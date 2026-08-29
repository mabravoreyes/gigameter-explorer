"""
Traceroute data loading and AS-path reshaping.

Reads the monthly M-Lab traceroute exports committed under
`data/traceroutes/<ISO2>/` and turns them into frames the notebooks can use.
Notebooks should use load_traceroutes() rather than reading parquet directly:
the exports carry BigQuery `dbdate` pandas metadata that breaks a plain
pd.read_parquet(), and the hop details need flattening before they are useful.

Usage — from a notebook:
    import sys
    sys.path.insert(0, 'helpers')
    from load_traceroutes import (
        load_traceroutes, hop_frame, upstream_adjacency,
        provider_summary, upstream_concentration,
    )

    tr    = load_traceroutes('AL')            # all published months
    hops  = hop_frame(tr)                     # one row per hop
    up    = upstream_adjacency(tr)            # one row per completed path
    provider_summary(tr)                      # access-ISP mix by month
    upstream_concentration(up)                # transit mix + HHI by ISP

Direction of measurement — read this before interpreting a path.
M-Lab runs the traceroute *from its server towards the client*, so
`forward_updated_node_details` starts at `dst_asn` (the server's host network)
and ends at `src_asn` (the client's network). `src_*` describes the client in
Albania; `dst_*` describes the M-Lab server. `is_reaching_dst_asn` means the
trace completed all the way into the client's ASN — the "destination" in that
field name is the traceroute's target, i.e. the client.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "traceroutes"

# Hop entries whose ASN is unresolved ('*' replies) carry this RTT sentinel.
_NO_REPLY_RTT = -1.0


def data_dir(country: str = "AL", data_root: Path | str | None = None) -> Path:
    """Where a country's exports live; `data_root` overrides the committed tree."""
    return Path(data_root or _DATA_ROOT) / country.upper()


def manifest(country: str = "AL", data_root: Path | str | None = None) -> dict:
    """Provenance for the exports: source URL, rows, sha256 per month."""
    return json.loads((data_dir(country, data_root) / "manifest.json").read_text())


def load_traceroutes(
    country: str = "AL",
    months: list[str] | None = None,
    columns: list[str] | None = None,
    data_root: Path | str | None = None,
) -> pd.DataFrame:
    """
    Concatenate the monthly exports for `country` into one frame.

    months  — e.g. ['2026-05', '2026-06']; None loads every published month.
    columns — subset to read; None reads all. The two node-detail columns are
              large, so pass a subset when you only need the row-level fields.
    data_root — read from here instead of the committed `data/traceroutes/`,
              e.g. a bulk pull cached under `cache/`.

    Empty exports (a month the site published with zero rows) are skipped, and
    a `month` column is added so per-month grouping does not need re-parsing.
    """
    d = data_dir(country, data_root)
    if not d.exists():
        raise FileNotFoundError(f"No committed traceroutes for {country!r} at {d}")

    frames = []
    for path in sorted(d.glob(f"giga_{country.upper()}_*.parquet")):
        table = pq.read_table(path, columns=columns)
        if table.num_rows == 0:
            continue
        # to_pandas(ignore_metadata=True) sidesteps the BigQuery 'dbdate'
        # numpy_type in the file's pandas metadata, which pandas cannot parse.
        frame = table.to_pandas(ignore_metadata=True)
        # A few exports carry pandas' index column and others do not; it holds
        # nothing, and keeping it would leave NaNs across a mixed concat.
        frame = frame.drop(columns="__index_level_0__", errors="ignore")
        frame["month"] = path.stem.rsplit("_", 1)[-1]
        frames.append(frame)

    if not frames:
        raise ValueError(f"Every export for {country!r} is empty")

    tr = pd.concat(frames, ignore_index=True)
    # partition_date is absent when the caller subsets `columns`.
    if "partition_date" in tr.columns:
        tr["partition_date"] = pd.to_datetime(tr["partition_date"])
    if months is not None:
        tr = tr[tr["month"].isin(months)].reset_index(drop=True)
    return tr


def as_path(hops) -> list[int]:
    """
    Collapse a hop list into an AS-level path.

    Unresolved hops are dropped and consecutive hops in the same AS are
    collapsed, so the result is the sequence of distinct networks the packets
    crossed, server first and client last.
    """
    path: list[int] = []
    for hop in hops if hops is not None else []:
        asn = hop.get("associated_asn")
        if asn and (not path or path[-1] != asn):
            path.append(asn)
    return path


def hop_frame(tr: pd.DataFrame, direction: str = "forward") -> pd.DataFrame:
    """
    Explode the node details into one row per hop.

    Keeps the row-level identifiers alongside each hop so hops can be grouped
    by month, access ISP or school without joining back.
    """
    column = f"{direction}_updated_node_details"
    keep = ["id", "month", "partition_date", "src_asn", "src_asn_name",
            "dst_asn", "dst_site", "ndt_rtt", "is_reaching_dst_asn"]

    rows = []
    for record in tr[keep + [column]].to_dict("records"):
        hops = record.pop(column)
        for position, hop in enumerate(hops if hops is not None else []):
            rows.append({
                **record,
                "hop_index": position,
                "ttl": hop.get("ttl"),
                "addr": hop.get("addr"),
                "hop_asn": hop.get("associated_asn"),
                "hop_org": hop.get("associated_org"),
                "hop_ixp": hop.get("associated_ixp"),
                "hop_cc": hop.get("cc"),
                "hop_place": hop.get("place"),
                "hop_rtt": hop.get("rtts"),
                "cumulative_distance_km": hop.get("cumulative_distance_km"),
            })

    hops = pd.DataFrame(rows)
    if not hops.empty:
        hops["responded"] = hops["hop_rtt"] != _NO_REPLY_RTT
    return hops


def upstream_adjacency(tr: pd.DataFrame) -> pd.DataFrame:
    """
    For each completed path, the AS immediately upstream of the client's own ASN.

    This is the transit relationship the access ISP actually buys. It is
    deliberately taken from the hop *adjacent to the client* rather than from
    the whole path: every trace starts at the same M-Lab server, so the early
    hops describe that server's connectivity and are common to all Albanian
    ISPs. Only the tail of the path distinguishes one provider from another.

    Rows whose trace did not reach the client's ASN are dropped, as are paths
    where the client's ASN is the first resolved hop and has no visible upstream.
    """
    rows = []
    completed = tr[tr["is_reaching_dst_asn"].fillna(False)]
    for record in completed[["id", "month", "src_asn", "src_asn_name",
                             "forward_updated_node_details"]].to_dict("records"):
        path = as_path(record["forward_updated_node_details"])
        client = record["src_asn"]
        if client not in path:
            continue
        position = path.index(client)
        if position == 0:
            continue
        rows.append({
            "id": record["id"],
            "month": record["month"],
            "client_asn": client,
            "client_asn_name": record["src_asn_name"],
            "upstream_asn": path[position - 1],
            "as_path_length": len(path),
        })

    upstream = pd.DataFrame(rows)
    if not upstream.empty:
        lookup = asn_org_lookup(tr)
        upstream["upstream_org"] = upstream["upstream_asn"].map(lookup)
        # src_asn_name is unpopulated for some networks; the hop annotations
        # name them, so fall back to those rather than reporting a bare ASN.
        upstream["client_asn_name"] = (upstream["client_asn_name"]
                                       .fillna(upstream["client_asn"].map(lookup)))
    return upstream


def asn_org_lookup(tr: pd.DataFrame) -> dict[int, str]:
    """Map ASN -> organisation name, harvested from every annotated hop."""
    lookup: dict[int, str] = {}
    for hops in tr["forward_updated_node_details"]:
        for hop in hops if hops is not None else []:
            asn, org = hop.get("associated_asn"), hop.get("associated_org")
            if asn and org:
                lookup[asn] = org
    return lookup


def _hhi(shares: pd.Series) -> float:
    """Herfindahl-Hirschman index on percentage shares (0-10,000)."""
    percentages = shares / shares.sum() * 100
    return float((percentages ** 2).sum())


def provider_summary(tr: pd.DataFrame) -> pd.DataFrame:
    """
    Access-ISP mix per month: how many networks are observed, how concentrated
    they are, and the leading provider's share.
    """
    out = []
    for month, group in tr.groupby("month"):
        counts = group["src_asn"].value_counts()
        leader = counts.index[0]
        name = group.loc[group["src_asn"] == leader, "src_asn_name"].dropna()
        out.append({
            "month": month,
            "traceroutes": len(group),
            "access_asns": counts.size,
            "hhi": round(_hhi(counts)),
            "top_asn": leader,
            "top_asn_name": name.iloc[0] if len(name) else None,
            "top_share_pct": round(100 * counts.iloc[0] / counts.sum(), 1),
        })
    return pd.DataFrame(out).sort_values("month").reset_index(drop=True)


def upstream_concentration(upstream: pd.DataFrame, min_paths: int = 50) -> pd.DataFrame:
    """
    Per access ISP per month: how many distinct upstreams are visible, how
    concentrated they are, and the dominant transit provider's share.

    ISPs with fewer than `min_paths` completed traces in a month are dropped —
    a handful of traces cannot support a concentration claim.
    """
    out = []
    for (month, asn), group in upstream.groupby(["month", "client_asn"]):
        if len(group) < min_paths:
            continue
        counts = group["upstream_asn"].value_counts()
        top = counts.index[0]
        names = group["client_asn_name"].dropna()
        orgs = group.loc[group["upstream_asn"] == top, "upstream_org"].dropna()
        out.append({
            "month": month,
            "client_asn": asn,
            "client_asn_name": names.iloc[0] if len(names) else None,
            "completed_paths": len(group),
            "upstreams": counts.size,
            "hhi": round(_hhi(counts)),
            "top_upstream_asn": top,
            "top_upstream_org": orgs.iloc[0] if len(orgs) else None,
            "top_upstream_share_pct": round(100 * counts.iloc[0] / counts.sum(), 1),
        })
    columns = ["month", "client_asn", "client_asn_name", "completed_paths",
               "upstreams", "hhi", "top_upstream_asn", "top_upstream_org",
               "top_upstream_share_pct"]
    if not out:
        # A small country can have no ISP-month clearing min_paths. Return the
        # empty frame with its columns so callers can filter it like any other.
        return pd.DataFrame(columns=columns)
    return (pd.DataFrame(out, columns=columns)
            .sort_values(["month", "completed_paths"], ascending=[True, False])
            .reset_index(drop=True))


def latency_decomposition(tr: pd.DataFrame, home_cc: str) -> pd.DataFrame:
    """
    Split each path's round-trip time into the part accrued inside the country
    and the part accrued crossing borders.

    Hop RTTs are cumulative from the server, so the difference between
    consecutive responding hops is that link's contribution. A link counts as
    domestic only when both of its endpoints geolocate to `home_cc`; anything
    touching another country is international. Non-responding hops ('*',
    rtts = -1) are skipped, and the occasional negative delta — routers answer
    out of order — is clamped to zero rather than allowed to subtract latency.

    Returns one row per completed path with domestic_ms, international_ms and
    their share of the total, alongside the measured ndt_rtt for comparison.
    """
    rows = []
    completed = tr[tr["is_reaching_dst_asn"].fillna(False)]
    for record in completed[["id", "month", "src_asn_name", "ndt_rtt",
                             "ndt_loss_rate",
                             "forward_updated_node_details"]].to_dict("records"):
        hops = record["forward_updated_node_details"]
        responding = [h for h in (hops if hops is not None else [])
                      if h.get("rtts") is not None and h["rtts"] != _NO_REPLY_RTT]
        if len(responding) < 2:
            continue

        domestic = international = 0.0
        for previous, hop in zip(responding, responding[1:]):
            delta = max(0.0, hop["rtts"] - previous["rtts"])
            if previous.get("cc") == home_cc and hop.get("cc") == home_cc:
                domestic += delta
            else:
                international += delta

        total = domestic + international
        if total <= 0:
            continue
        rows.append({
            "id": record["id"],
            "month": record["month"],
            "isp": record["src_asn_name"],
            "ndt_rtt": record["ndt_rtt"],
            "loss_rate": record["ndt_loss_rate"],
            "domestic_ms": round(domestic, 2),
            "international_ms": round(international, 2),
            "international_pct": round(100 * international / total, 1),
        })
    return pd.DataFrame(rows)
