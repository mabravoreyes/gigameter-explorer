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
