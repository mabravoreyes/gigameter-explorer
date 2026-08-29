"""
Cross-country profile of the traceroute exports.

Summarises every country in one row so a case study can be chosen on evidence
rather than on which files happened to be downloaded: how concentrated the
access market is, who carries the transit, how far the traffic travels, and
whether the panel looks like schools.

Usage — from the command line:
    python helpers/fetch_traceroutes.py --all --dest cache/traceroutes --max-mb 70
    python helpers/traceroute_profiles.py --root cache/traceroutes

Usage — from a notebook:
    import sys; sys.path.insert(0, 'helpers')
    from traceroute_profiles import profile_all, read_profiles
    profiles = profile_all('cache/traceroutes')     # recompute from parquet
    profiles = read_profiles()                      # or read the saved CSV

Read the saved CSV with read_profiles(), never a bare pd.read_csv: Namibia's
ISO-2 code is "NA", which pandas turns into a missing value by default and
would drop the country from any grouping.

Every figure is descriptive of one country's own paths. RTT and path length are
NOT comparable across countries — each country is measured against whichever
M-Lab servers serve it, so a low median means "close to its server", not
"better connected". The concentration measures are comparable; the distances
are not.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import pandas as pd

from load_traceroutes import (
    load_traceroutes, as_path, upstream_adjacency, upstream_concentration,
)

# A trace-weighted HHI above this is "highly concentrated" under the merger
# guidelines the term comes from; used only to label, never to filter.
_CONCENTRATED = 2_500


def read_profiles(path: Path | str = "data/traceroutes/country_profiles.csv") -> pd.DataFrame:
    """
    Load the saved profile table.

    `keep_default_na=False` on the country column is not optional: Namibia is
    "NA" and pandas would otherwise read it as a missing value.
    """
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def _hhi(counts: pd.Series) -> float:
    shares = counts / counts.sum() * 100
    return float((shares ** 2).sum())


def _local_hour_offset(tr: pd.DataFrame) -> int:
    """
    Approximate the country's UTC offset from client longitude.

    Avoids carrying a timezone table for 28 countries; good to the hour, which
    is all the school-hours test needs.
    """
    lon = tr["src_lon"].dropna()
    return int(round(lon.median() / 15)) if len(lon) else 0


def profile_country(country: str, root: Path | str) -> dict | None:
    """One summary row for `country`, or None if nothing loadable is on disk."""
    try:
        tr = load_traceroutes(country, data_root=root)
    except (FileNotFoundError, ValueError):
        return None

    row: dict = {
        "country": country,
        "months": tr["month"].nunique(),
        "traces": len(tr),
    }

    # --- access market ---
    access = tr["src_asn"].value_counts()
    leader = tr.loc[tr["src_asn"] == access.index[0], "src_asn_name"].dropna()
    row.update(
        access_asns=access.size,
        access_hhi=round(_hhi(access)),
        top_access_share=round(100 * access.iloc[0] / access.sum(), 1),
        top_access_name=(leader.iloc[0] if len(leader) else f"AS{access.index[0]}"),
    )

    # --- does the panel look like schools? ---
    offset = _local_hour_offset(tr)
    hour = (tr["window_start"].dt.hour + offset) % 24
    weekday = tr["window_start"].dt.dayofweek < 5
    in_school = weekday & hour.between(8, 15)
    row.update(
        utc_offset=offset,
        school_hours_pct=round(100 * in_school.mean(), 1),
        weekend_pct=round(100 * (~weekday).mean(), 1),
    )

    # --- path completion and transit ---
    row["completed_pct"] = round(100 * tr["is_reaching_dst_asn"].fillna(False).mean(), 1)
    upstream = upstream_adjacency(tr)
    if upstream.empty:
        row.update(transit_hhi=None, top_upstream_org=None, top_upstream_share=None,
                   single_homed_pct=None)
    else:
        counts = upstream["upstream_asn"].value_counts()
        top_org = upstream.loc[upstream["upstream_asn"] == counts.index[0],
                               "upstream_org"].dropna()
        conc = upstream_concentration(upstream, min_paths=50)
        row.update(
            transit_hhi=round(_hhi(counts)),
            top_upstream_org=(top_org.iloc[0] if len(top_org) else f"AS{counts.index[0]}"),
            top_upstream_share=round(100 * counts.iloc[0] / counts.sum(), 1),
            single_homed_pct=(round(100 * (conc["top_upstream_share_pct"] >= 90).mean(), 1)
                              if len(conc) else None),
        )

    # --- geography, on completed paths only ---
    done = tr[tr["is_reaching_dst_asn"].fillna(False)]
    row["median_path_km"] = round(done["forward_distance"].median()) if len(done) else None
    row["median_rtt_ms"] = round(done["ndt_rtt"].median(), 1) if len(done) else None

    crossed = []
    for hops in done["forward_updated_node_details"]:
        codes = {h["cc"] for h in (hops if hops is not None else []) if h["cc"]}
        if codes:
            crossed.append(len(codes))
    row["median_countries_crossed"] = int(pd.Series(crossed).median()) if crossed else None

    sites = tr["dst_site"].value_counts()
    row["top_site"] = sites.index[0] if sites.size else None
    row["top_site_share"] = round(100 * sites.iloc[0] / sites.sum(), 1) if sites.size else None
    return row


def profile_all(root: Path | str = "cache/traceroutes") -> pd.DataFrame:
    """Profile every country directory under `root`."""
    root = Path(root)
    rows = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        print(f"  {directory.name} ...", end="", flush=True)
        row = profile_country(directory.name, root)
        print(" ok" if row else " skipped (no loadable months)")
        if row:
            rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--root", default="cache/traceroutes")
    parser.add_argument("--out", default="data/traceroutes/country_profiles.csv")
    args = parser.parse_args(argv)

    profiles = profile_all(args.root)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}  ({len(profiles)} countries)")

    partial = profiles[profiles["months"] < 6]
    if len(partial):
        print("\nPartial coverage — fewer than 6 months on disk, so these rows "
              "describe\nwhat was fetched rather than what the site publishes:")
        for _, r in partial.iterrows():
            print(f"   {r['country']}: {r['months']} months, {r['traces']:,} traces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
