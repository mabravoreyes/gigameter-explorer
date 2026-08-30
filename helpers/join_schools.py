"""
Attach school identity to traceroutes via the NDT UUID.

The published traceroute exports carry no school identity: `client_ip` is an
address, and the country reports are explicit that counting addresses misstates
school counts ("one IP is not one school"). The `id` column is the NDT test
UUID, which the Giga Meter measurements also carry as `measurement_uuid`, so a
join on it attributes each traceroute to the school that produced it.

Usage — from a notebook:
    import sys; sys.path.insert(0, 'helpers')
    from join_schools import school_index, attach_schools

    idx = school_index('BLZ', '2026-07-01', '2026-07-31')   # cached after first call
    tr  = attach_schools(load_traceroutes('BZ', months=['2026-07']), idx)
    tr['school_id_giga'].nunique()

Requires Trino (see the repo README for the port-forward). Results are cached
under `cache/<ISO3>/school_index_<start>_<end>.parquet`, so a notebook re-run
does not re-query.

This does NOT reproduce the published reports' "known school IP ranges" filter,
which is a curated list not present in the measurement data — for Belize in
July 2026 the reports keep 889 rows from 28 school IPs, where this join keeps
1,040 from 32 schools. The join is the better instrument for per-school
questions even so: it yields school identity rather than addresses, and it is
what the reports' own School-Level Study uses.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_CACHE_ROOT = Path(__file__).resolve().parent.parent / "cache"

# Columns worth carrying onto a traceroute. Everything else in the measurement
# table describes the NDT transfer, which the traceroute row already has. The
# wifi_* and detected_location_* fields are what `wifi_analysis` needs: they
# describe the link inside the school and how far the client sat from it,
# neither of which exists in the traceroute exports.
_INDEX_COLUMNS = """
    measurement_uuid, school_id_giga, school_name, school_id_govt,
    ip_address, isp_name_clean, isp_asn_clean, admin1, admin2,
    education_level, school_area_type, latitude, longitude,
    download_speed, upload_speed, latency, packet_loss_rate,
    connectivity_type, pass_fail_overall,
    wifi_ssid, wifi_model, wifi_quality, wifi_signal,
    wifi_tx_rate, wifi_channel, wifi_frequency,
    detected_location_distance, detected_location_is_flagged
"""


def school_index(
    iso3: str,
    start: str,
    end: str,
    cursor=None,
    use_cached: bool = True,
) -> pd.DataFrame:
    """
    One row per Giga Meter measurement in the window, keyed by NDT UUID.

    iso3        — e.g. 'BLZ'; matches `iso3_code` in the measurement table.
    start, end  — inclusive ISO dates, e.g. '2026-07-01', '2026-07-31'.
    use_cached  — read the cached parquet if it exists rather than re-querying.
    """
    iso3 = iso3.upper()
    cache = _CACHE_ROOT / iso3
    path = cache / f"school_index_{start}_{end}.parquet"
    if use_cached and path.exists():
        return pd.read_parquet(path)

    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    cursor.execute(f"""
        SELECT {_INDEX_COLUMNS}
        FROM all_gigameter_measurement_data
        WHERE iso3_code = '{iso3}'
          AND date >= DATE '{start}' AND date <= DATE '{end}'
    """)
    index = pd.DataFrame(cursor.fetchall(),
                         columns=[d[0] for d in cursor.description])

    cache.mkdir(parents=True, exist_ok=True)
    index.to_parquet(path, index=False)
    return index


def attach_schools(tr: pd.DataFrame, index: pd.DataFrame,
                   how: str = "inner") -> pd.DataFrame:
    """
    Join traceroutes to the school index on the NDT UUID.

    `how='inner'` keeps only attributed traceroutes, which is what any
    per-school figure needs. `how='left'` keeps everything and leaves
    `school_id_giga` null where the Giga Meter backend has no record of the
    test — useful for measuring attribution coverage.
    """
    joined = tr.merge(index, left_on="id", right_on="measurement_uuid", how=how)
    return joined.drop(columns="measurement_uuid", errors="ignore")


def attribution_summary(tr: pd.DataFrame, index: pd.DataFrame) -> dict:
    """Coverage of the join: how much of the traceroute set carries a school."""
    joined = attach_schools(tr, index, how="left")
    attributed = joined["school_id_giga"].notna()
    return {
        "traceroutes": len(tr),
        "attributed": int(attributed.sum()),
        "attributed_pct": round(100 * attributed.mean(), 1),
        "schools": int(joined.loc[attributed, "school_id_giga"].nunique()),
        "schools_measuring": int(index["school_id_giga"].nunique()),
        "client_ips": int(tr["client_ip"].nunique()),
        "ips_per_school": round(
            joined.loc[attributed].groupby("school_id_giga")["client_ip"].nunique().mean(), 2),
        "schools_per_ip": round(
            joined.loc[attributed].groupby("client_ip")["school_id_giga"].nunique().mean(), 2),
    }


def schools_behind_upstream(joined: pd.DataFrame, upstream: pd.DataFrame) -> pd.DataFrame:
    """
    Count *schools*, not traces, behind each transit provider.

    `joined` is attach_schools() output; `upstream` is upstream_adjacency()
    output. This is the figure a ministry can act on — "N schools depend on one
    transit provider" — and it cannot be produced from the traceroute files
    alone.
    """
    merged = joined.merge(upstream[["id", "upstream_asn", "upstream_org"]], on="id")
    out = (merged.groupby(["upstream_asn", "upstream_org"])
                 .agg(schools=("school_id_giga", "nunique"),
                      traces=("id", "size"))
                 .reset_index()
                 .sort_values("schools", ascending=False))
    out["school_pct"] = (100 * out["schools"]
                         / merged["school_id_giga"].nunique()).round(1)
    return out.reset_index(drop=True)


def balanced_panel(joined: pd.DataFrame, month_a: str, month_b: str,
                   metric: str = "ndt_rtt", min_tests: int = 3) -> dict:
    """
    Compare two months over the schools present in both, not over whatever was
    measuring at the time.

    A fleet that is still being rolled out changes composition every month, and
    a country-level median then moves for two unrelated reasons: schools
    performing differently, and different schools being measured. Restricting to
    the schools common to both months removes the second, leaving the change a
    school actually experienced.

    Returns the naive change, the balanced change, and the gap between them —
    which is the part of the headline that was composition.
    """
    frame = joined[joined["month"].isin([month_a, month_b])]
    frame = frame[frame[metric].notna()]

    per = (frame.groupby(["school_id_giga", "month"])[metric]
                .agg(["median", "size"]).reset_index())
    per = per[per["size"] >= min_tests]
    wide = per.pivot(index="school_id_giga", columns="month", values="median")
    if month_a not in wide.columns or month_b not in wide.columns:
        return {}
    both = wide.dropna(subset=[month_a, month_b])

    naive_a = frame.loc[frame["month"] == month_a, metric].median()
    naive_b = frame.loc[frame["month"] == month_b, metric].median()

    out = {
        "month_a": month_a, "month_b": month_b,
        "schools_a": int(wide[month_a].notna().sum()),
        "schools_b": int(wide[month_b].notna().sum()),
        "schools_both": len(both),
        "naive_a": round(float(naive_a), 1),
        "naive_b": round(float(naive_b), 1),
        "naive_change_pct": round(100 * (naive_b / naive_a - 1), 1) if naive_a else None,
    }
    if len(both) >= 5:
        bal_a, bal_b = both[month_a].median(), both[month_b].median()
        out.update({
            "balanced_a": round(float(bal_a), 1),
            "balanced_b": round(float(bal_b), 1),
            "balanced_change_pct": round(100 * (bal_b / bal_a - 1), 1) if bal_a else None,
            "median_school_delta": round(float((both[month_b] - both[month_a]).median()), 1),
            "schools_improved_pct": round(100 * float((both[month_b] < both[month_a]).mean()), 1),
        })
        if out["naive_change_pct"] is not None and out["balanced_change_pct"] is not None:
            out["composition_pp"] = round(out["naive_change_pct"] - out["balanced_change_pct"], 1)
    return out
