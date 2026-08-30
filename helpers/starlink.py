"""
Starlink as a school connectivity provider.

Giga Meter records the ISP behind each measurement, so Starlink adoption can be
tracked per country and month, and — where traceroute exports exist — its
routing compared against the terrestrial operators in the same country.

    import sys; sys.path.insert(0, 'helpers')
    from starlink import penetration, STARLINK_SQL, is_starlink

    adoption = penetration()          # country x month, cached

Identification keys on the operator name, not the ASN. The measurements carry
`AS14593` and `AS1459` under an identical operator name, the second almost
certainly a corrupted ASN string rather than a different network, and a
handful of rows carry no ASN at all. The name is the field that is consistent.
It also arrives with a trailing space on most rows, so an equality test on it
silently drops the majority — every match here is by lowercased substring.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_CACHE = Path(__file__).resolve().parent.parent / "cache"

# Substrings that identify the operator in `isp_name`. "starlink" catches the
# SPACEX-STARLINK rows; "space explor" catches the corporate name.
STARLINK_PATTERNS = ("space explor", "starlink", "spacex")

STARLINK_SQL = ("(lower(isp_name) LIKE '%space explor%' "
                "OR lower(isp_name) LIKE '%starlink%' "
                "OR lower(isp_name) LIKE '%spacex%')")


def is_starlink(series: pd.Series) -> pd.Series:
    """Boolean mask over an ISP-name column, matching the SQL filter above."""
    lowered = series.fillna("").str.lower()
    mask = pd.Series(False, index=series.index)
    for pattern in STARLINK_PATTERNS:
        mask |= lowered.str.contains(pattern, regex=False)
    return mask


def penetration(start: str = "2023-01-01", end: str = "2026-08-31",
                cursor=None, use_cached: bool = True) -> pd.DataFrame:
    """
    Starlink share of school measurement, by country and month.

    Reported in schools as well as tests: a single school testing heavily would
    otherwise read as adoption. `schools_total` is every school measuring in
    that country-month, so the share is against the measured estate rather than
    against the school census, which Giga Meter does not cover.
    """
    path = _CACHE / f"starlink_penetration_{start}_{end}.parquet"
    if use_cached and path.exists():
        return pd.read_parquet(path)

    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    cursor.execute(f"""
        SELECT iso3_code,
               date_trunc('month', date) AS month,
               count(*)                                        AS tests_total,
               count(DISTINCT school_id_giga)                  AS schools_total,
               count_if({STARLINK_SQL})                        AS tests_starlink,
               count(DISTINCT CASE WHEN {STARLINK_SQL}
                                   THEN school_id_giga END)    AS schools_starlink,
               count(DISTINCT isp_name)                        AS isps_total
        FROM all_gigameter_measurement_data
        WHERE date >= DATE '{start}' AND date <= DATE '{end}'
        GROUP BY iso3_code, date_trunc('month', date)
    """)
    frame = pd.DataFrame(cursor.fetchall(),
                         columns=[d[0] for d in cursor.description])
    frame["month"] = pd.to_datetime(frame["month"]).dt.strftime("%Y-%m")
    frame["school_share_pct"] = (100 * frame["schools_starlink"]
                                 / frame["schools_total"]).round(1)
    frame["test_share_pct"] = (100 * frame["tests_starlink"]
                               / frame["tests_total"]).round(1)
    frame = frame.sort_values(["iso3_code", "month"]).reset_index(drop=True)

    _CACHE.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


def adoption_summary(pen: pd.DataFrame, min_schools: int = 10) -> pd.DataFrame:
    """
    One row per country: when Starlink first appeared, and where it stands.

    Months in which a country measured fewer than `min_schools` are dropped
    before the first-seen date is taken, so a single stray measurement does not
    date an arrival.
    """
    solid = pen[pen["schools_total"] >= min_schools]
    rows = []
    for iso3, group in solid.groupby("iso3_code"):
        group = group.sort_values("month")
        live = group[group["schools_starlink"] > 0]
        if live.empty:
            continue
        latest = group.iloc[-1]
        peak = group.loc[group["school_share_pct"].idxmax()]
        rows.append({
            "iso3": iso3,
            "first_seen": live.iloc[0]["month"],
            "months_present": int((group["schools_starlink"] > 0).sum()),
            "months_observed": len(group),
            "schools_latest": int(latest["schools_starlink"]),
            "schools_total_latest": int(latest["schools_total"]),
            "share_latest_pct": float(latest["school_share_pct"]),
            "share_peak_pct": float(peak["school_share_pct"]),
            "peak_month": peak["month"],
            "latest_month": latest["month"],
        })
    return (pd.DataFrame(rows).sort_values("share_latest_pct", ascending=False)
            .reset_index(drop=True))


def compare_routing(tr: pd.DataFrame, country_iso2: str, min_traces: int = 100) -> pd.DataFrame:
    """
    Starlink against terrestrial routing in one country, destination held fixed.

    Restricted to the country's modal M-Lab server, because Starlink and
    terrestrial clients do not always select the same one and comparing across
    servers would compare destinations rather than networks.

    Returns one row per kind: latency, throughput, loss, path geography, the
    dominant transit provider, and how often the trace completes.
    """
    from load_traceroutes import (upstream_adjacency, country_sequences,
                                  latency_decomposition)

    site = tr["dst_site"].value_counts().idxmax()
    fixed = tr[tr["dst_site"] == site]
    starlink = is_starlink(fixed["src_asn_name"])
    upstream = upstream_adjacency(fixed)
    sequences = country_sequences(fixed, country_iso2)

    rows = []
    for label, subset in (("starlink", fixed[starlink]),
                          ("terrestrial", fixed[~starlink])):
        if len(subset) < min_traces:
            continue
        done = subset[subset["is_reaching_dst_asn"].fillna(False)]
        seq = sequences.reindex(subset.index).dropna()
        ups = upstream[upstream["id"].isin(subset["id"])]["upstream_org"].value_counts()
        decomposition = latency_decomposition(subset, country_iso2)
        rows.append({
            "kind": label, "site": site, "traces": len(subset),
            "median_rtt_ms": round(float(subset["ndt_rtt"].median()), 1),
            "median_mbps": round(float(subset["ndt_throughput"].median()), 1),
            "median_loss_pct": round(100 * float(subset["ndt_loss_rate"].median()), 2),
            "median_path_km": round(float(done["forward_distance"].median())) if len(done) else None,
            "countries_crossed": round(float(seq.map(len).median()), 1) if len(seq) else None,
            "completion_pct": round(100 * float(subset["is_reaching_dst_asn"].mean()), 1),
            "top_upstream": ups.index[0] if len(ups) else None,
            "top_upstream_pct": round(100 * float(ups.iloc[0] / ups.sum()), 1) if len(ups) else None,
            "domestic_ms": round(float(decomposition["domestic_ms"].median()), 2) if len(decomposition) else None,
            "international_ms": round(float(decomposition["international_ms"].median()), 1) if len(decomposition) else None,
            "top_route": " -> ".join(seq.value_counts().idxmax()) if len(seq) else None,
        })
    return pd.DataFrame(rows)


def congestion_profile(start: str = "2026-01-01", countries: list[str] | None = None,
                       cursor=None, use_cached: bool = True) -> pd.DataFrame:
    """
    Performance by local hour, split by Starlink and terrestrial.

    A wide swing across the school day means capacity is contended. Comparing
    the two kinds *within* a country holds the schools, the calendar and the
    destination roughly constant, so the difference is the access technology.
    """
    key = "-".join(sorted(countries)) if countries else "all"
    path = _CACHE / f"starlink_congestion_{key}_{start}.parquet"
    if use_cached and path.exists():
        return pd.read_parquet(path)

    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    clause = ""
    if countries:
        clause = "AND iso3_code IN ('" + "','".join(countries) + "')"
    cursor.execute(f"""
        SELECT iso3_code,
               CASE WHEN {STARLINK_SQL} THEN 'starlink' ELSE 'terrestrial' END AS kind,
               local_hour_of_measurement AS hour,
               count(*) AS tests,
               approx_percentile(download_speed, 0.5) AS median_mbps,
               approx_percentile(CAST(latency AS DOUBLE), 0.5) AS median_rtt,
               approx_percentile(CAST(packet_loss_rate AS DOUBLE), 0.5) AS median_loss
        FROM all_gigameter_measurement_data
        WHERE date >= DATE '{start}' {clause}
          AND local_hour_of_measurement BETWEEN 7 AND 17
        GROUP BY 1, 2, 3
    """)
    frame = pd.DataFrame(cursor.fetchall(),
                         columns=[d[0] for d in cursor.description])
    _CACHE.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


def congestion_summary(profile: pd.DataFrame, min_tests: int = 50,
                       min_hours: int = 5) -> pd.DataFrame:
    """Best against worst school hour, per country and access kind."""
    solid = profile[profile["tests"] >= min_tests]
    rows = []
    for (iso3, kind), group in solid.groupby(["iso3_code", "kind"]):
        if len(group) < min_hours:
            continue
        rows.append({
            "iso3": iso3, "kind": kind, "tests": int(group["tests"].sum()),
            "mbps_best": round(float(group["median_mbps"].max()), 1),
            "mbps_worst": round(float(group["median_mbps"].min()), 1),
            "mbps_swing_pct": round(100 * (group["median_mbps"].max() - group["median_mbps"].min())
                                    / group["median_mbps"].max()),
            "rtt_best": round(float(group["median_rtt"].min()), 1),
            "rtt_worst": round(float(group["median_rtt"].max()), 1),
            "median_loss_pct": round(100 * float(group["median_loss"].median()), 2),
        })
    return pd.DataFrame(rows).sort_values(["iso3", "kind"]).reset_index(drop=True)
