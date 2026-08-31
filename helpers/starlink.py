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


def ground_station_handoff(tr: pd.DataFrame) -> pd.DataFrame:
    """
    Where Starlink hands traffic to the terrestrial internet.

    Starlink backhauls to a ground station before entering the normal internet,
    and the first hop *after* the Starlink ASN is where that happens. That hop
    is the reliable signal: it belongs to a third-party network and geolocates
    on its own merits.

    The Starlink hops themselves are not reliable for this. A large share of
    them geolocate to Los Angeles or Hawthorne, California — SpaceX's
    registered address — which is what geolocation databases return when they
    know only the ASN's registration, not the prefix. Treat those as unknown
    rather than as a Californian ground station.

    Hops are stored server-to-client, so the walk is reversed to run outward
    from the school.
    """
    rows = []
    for hops in tr["forward_updated_node_details"]:
        outward = list(hops if hops is not None else [])[::-1]
        seen_starlink = False
        for hop in outward:
            asn = hop.get("associated_asn")
            org = (hop.get("associated_org") or "")
            starlink_hop = (asn == 14593 or "space explor" in org.lower()
                            or "starlink" in org.lower())
            if starlink_hop:
                seen_starlink = True
            elif seen_starlink:
                rows.append({"handoff_org": org, "handoff_place": hop.get("place"),
                             "handoff_cc": (hop.get("cc") or "").upper(),
                             "handoff_asn": asn})
                break
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    out = (frame.groupby(["handoff_cc", "handoff_place", "handoff_org"])
                .size().rename("traces").reset_index()
                .sort_values("traces", ascending=False))
    out["pct"] = (100 * out["traces"] / out["traces"].sum()).round(1)
    return out.reset_index(drop=True)


def within_school_comparison(iso3: str, min_tests: int = 20, cursor=None,
                             use_cached: bool = True) -> pd.DataFrame:
    """
    Starlink against terrestrial *within the same school*.

    Comparing Starlink schools with terrestrial schools compares the schools as
    much as the technology — a deployment chooses where it goes, and in Malawi
    the Starlink estate is 75% rural against 53% for terrestrial. A school that
    measured on both links is its own control: same building, same region, same
    curriculum, and the connection is the only thing that changes.

    Requires `min_tests` on each link, since a handful of stray measurements on
    the other technology does not support a comparison.
    """
    # Cached like the other pulls: this is the figure the whole selection
    # correction rests on, and it should not vanish from the notebook because a
    # cluster credential expired.
    path = _CACHE / f"starlink_within_school_{iso3.upper()}_{min_tests}.parquet"
    if use_cached and path.exists():
        return pd.read_parquet(path)

    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    cursor.execute(f"""
        SELECT school_id_giga, school_name, school_area_type,
               CASE WHEN {STARLINK_SQL} THEN 'starlink' ELSE 'terrestrial' END AS kind,
               count(*) AS tests,
               approx_percentile(download_speed, 0.5) AS median_mbps,
               approx_percentile(CAST(latency AS DOUBLE), 0.5) AS median_rtt,
               approx_percentile(CAST(packet_loss_rate AS DOUBLE), 0.5) AS median_loss
        FROM all_gigameter_measurement_data
        WHERE iso3_code = '{iso3.upper()}'
        GROUP BY 1, 2, 3, 4
    """)
    long = pd.DataFrame(cursor.fetchall(),
                        columns=[d[0] for d in cursor.description])
    wide = long.pivot_table(index=["school_id_giga", "school_name", "school_area_type"],
                            columns="kind",
                            values=["tests", "median_mbps", "median_rtt", "median_loss"],
                            aggfunc="first")
    wide.columns = [f"{a}_{b[:4]}" for a, b in wide.columns]
    both = wide.dropna(subset=["tests_star", "tests_terr"])
    solid = both[(both["tests_star"] >= min_tests) & (both["tests_terr"] >= min_tests)].copy()
    solid["mbps_gain"] = solid["median_mbps_star"] - solid["median_mbps_terr"]
    solid["rtt_gain"] = solid["median_rtt_terr"] - solid["median_rtt_star"]
    solid["loss_delta"] = solid["median_loss_star"] - solid["median_loss_terr"]
    out = solid.reset_index().sort_values("mbps_gain", ascending=False)
    _CACHE.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def within_school_verdict(comparison: pd.DataFrame) -> dict:
    """Does Starlink beat the same school's terrestrial link, and by how much?"""
    if comparison.empty:
        return {}
    from scipy import stats
    return {
        "schools": len(comparison),
        "median_mbps_terrestrial": round(float(comparison["median_mbps_terr"].median()), 2),
        "median_mbps_starlink": round(float(comparison["median_mbps_star"].median()), 2),
        "median_mbps_gain": round(float(comparison["mbps_gain"].median()), 2),
        "schools_faster_on_starlink": int((comparison["mbps_gain"] > 0).sum()),
        "median_rtt_gain_ms": round(float(comparison["rtt_gain"].median()), 1),
        "schools_lower_latency_on_starlink": int((comparison["rtt_gain"] > 0).sum()),
        "wilcoxon_p_mbps": (float(stats.wilcoxon(comparison["mbps_gain"]).pvalue)
                            if len(comparison) > 5 else None),
    }


def domestic_transit(tr: pd.DataFrame, country_iso2: str) -> dict:
    """
    Does school traffic enter its own country's internet, or leave without
    touching it?

    Only the hop where Starlink hands traffic over answers this, and only when
    something is observable there. Two cases make it unreadable and are
    excluded rather than counted:

    * the hand-off hop *is* the destination's own network, so nothing sits
      between the ground station and the server to see;
    * the AS path is two networks long, which is the same situation.

    Counting any domestic hop anywhere in the path — an earlier version of this
    function did — measures the wrong thing. Where the M-Lab server is itself
    domestic, the hops near it are the destination's own network and have
    nothing to do with the school's uplink. Mongolia reads 89% on that measure
    and 0% here: its domestic hops sit at position 0.20 of the path, the server
    end, while the school's traffic leaves for Tokyo without touching a
    Mongolian network. Kazakhstan is the reverse, with its domestic hops at
    position 0.85, the school end, and a server in Pakistan.

    `unreadable_pct` is part of the answer, not a footnote: Kenya is 85%
    unreadable because its server sits one hop from the ground station.
    """
    def _is_starlink_hop(hop) -> bool:
        asn = hop.get("associated_asn")
        org = (hop.get("associated_org") or "").lower()
        return asn == 14593 or "space explor" in org or "starlink" in org

    home = country_iso2.upper()
    traces = readable = domestic = unreadable = 0
    networks: dict[tuple, int] = {}

    for hops, destination_asn in zip(tr["forward_updated_node_details"], tr["dst_asn"]):
        sequence = list(hops if hops is not None else [])
        if not sequence:
            continue
        traces += 1

        as_path = []
        for hop in sequence:
            asn = hop.get("associated_asn")
            if asn and (not as_path or as_path[-1] != asn):
                as_path.append(asn)

        handoff, seen_starlink = None, False
        for hop in sequence[::-1]:          # stored server-to-client; walk outward
            if _is_starlink_hop(hop):
                seen_starlink = True
            elif seen_starlink:
                handoff = hop
                break
        if handoff is None:
            continue

        if handoff.get("associated_asn") == destination_asn or len(as_path) <= 2:
            unreadable += 1
            continue

        readable += 1
        if (handoff.get("cc") or "").upper() == home:
            domestic += 1
            key = (handoff.get("associated_org") or "unknown", handoff.get("place"))
            networks[key] = networks.get(key, 0) + 1

    top = sorted(networks.items(), key=lambda kv: -kv[1])[:5]
    return {
        "traces": traces,
        "unreadable_pct": round(100 * unreadable / traces, 1) if traces else None,
        "readable_traces": readable,
        "domestic_handoff_pct": round(100 * domestic / readable, 1) if readable else None,
        "domestic_networks": [{"org": o, "place": p, "traces": n} for (o, p), n in top],
    }
