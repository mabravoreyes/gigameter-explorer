"""
The Wi-Fi link inside the school.

Every other traceroute analysis measures the network between the school and an
M-Lab server. This one looks at the last few metres: the Giga Meter client
records the Wi-Fi it was connected to when the test ran, so a poor result can
be checked against the radio that carried it before it is blamed on routing.

These fields live in the Giga Meter measurements, not in the traceroute
exports, so they arrive through the same UUID join as `join_schools`:

    import sys; sys.path.insert(0, 'helpers')
    from join_schools import school_index, attach_schools
    from wifi_analysis import classify_wifi, wifi_estate, wifi_bottleneck

    joined = attach_schools(tr, school_index('BLZ', '2026-07-01', '2026-07-31'))
    wifi   = classify_wifi(joined)

Two limits to carry. Tests on Ethernet report no Wi-Fi at all, so this is a
subset and not a census of school networks. And `wifi_model` is the *client's*
adapter, not the access point — the negotiated rate reflects the weaker of the
two radios, so a modern client on an old AP reads as the old generation, which
is the honest answer for what the link could carry.
"""

from __future__ import annotations

import re

import pandas as pd

# Generation is not a column; it is announced in the adapter name. Ordered
# newest first so "Wi-Fi 6 ... 802.11ac compatible" resolves to the newer one.
_GENERATION_PATTERNS = [
    ("802.11ax", re.compile(r"802\.11ax|wi-?fi\s*6", re.I)),
    ("802.11ac", re.compile(r"802\.11ac|wireless[-\s]*ac|dual band.*ac", re.I)),
    ("802.11n",  re.compile(r"802\.11n|wireless[-\s]*n\b", re.I)),
]

# Band edges in MHz, as reported in wifi_frequency.
_BAND_EDGES = [(0, 3_000, "2.4 GHz"), (3_000, 5_925, "5 GHz"), (5_925, 1e9, "6 GHz")]

# Past this share of the negotiated rate a TCP transfer is plausibly limited by
# the radio rather than by the connection behind it.
_RADIO_LIMITED = 0.5


def _generation(model: object) -> str | None:
    if not isinstance(model, str):
        return None
    for label, pattern in _GENERATION_PATTERNS:
        if pattern.search(model):
            return label
    return None


def _band(frequency: object) -> str | None:
    if frequency is None or pd.isna(frequency):
        return None
    for low, high, label in _BAND_EDGES:
        if low <= float(frequency) < high:
            return label
    return None


def classify_wifi(joined: pd.DataFrame) -> pd.DataFrame:
    """
    Keep the tests that reported a Wi-Fi link and derive band, generation and
    how much of the negotiated radio rate the transfer actually used.

    A measured throughput above the negotiated rate is impossible on a single
    link and means the reported Wi-Fi was not the path under test; those rows
    are flagged `over_phy` so they can be excluded rather than allowed to
    inflate the ratio.
    """
    wifi = joined[joined["wifi_tx_rate"].notna()].copy()
    wifi["band"] = wifi["wifi_frequency"].map(_band)
    wifi["generation"] = wifi["wifi_model"].map(_generation)

    wifi["wifi_signal"] = pd.to_numeric(wifi["wifi_signal"], errors="coerce")
    wifi["download_speed"] = pd.to_numeric(wifi["download_speed"], errors="coerce")
    wifi["phy_ratio"] = wifi["download_speed"] / wifi["wifi_tx_rate"]
    wifi["over_phy"] = wifi["phy_ratio"] > 1
    wifi["radio_limited"] = wifi["phy_ratio"] >= _RADIO_LIMITED
    return wifi


def wifi_coverage(joined: pd.DataFrame, wifi: pd.DataFrame) -> dict:
    """How much of the attributed set reported a Wi-Fi link, and from how many schools."""
    return {
        "attributed_tests": len(joined),
        "with_wifi": len(wifi),
        "with_wifi_pct": round(100 * len(wifi) / len(joined), 1) if len(joined) else None,
        "schools_with_wifi": int(wifi["school_id_giga"].nunique()),
        "over_phy_tests": int(wifi["over_phy"].sum()),
    }


def measured_at_school(joined: pd.DataFrame) -> dict:
    """
    How far the client sat from the school Giga has registered.

    `detected_location_distance` is in metres and is populated on a minority of
    tests. This is the largest caveat on any school-level figure: a test taken
    kilometres away is not measuring that school's connection, and nothing else
    in the analysis corrects for it.
    """
    distance = pd.to_numeric(joined.get("detected_location_distance"),
                             errors="coerce").dropna() / 1000
    if distance.empty:
        return {"tests_with_location": 0}
    return {
        "tests_with_location": len(distance),
        "median_km": round(float(distance.median()), 2),
        "p90_km": round(float(distance.quantile(0.9)), 1),
        "max_km": round(float(distance.max()), 1),
        "beyond_10km": int((distance > 10).sum()),
    }


def wifi_estate(wifi: pd.DataFrame, min_tests: int = 5) -> pd.DataFrame:
    """
    The modal configuration per school, over schools with enough Wi-Fi tests.

    One row per school keeps a school that tested 200 times from outvoting one
    that tested six, which a per-test tally would allow.
    """
    counts = wifi.groupby("school_id_giga").size()
    keep = wifi[wifi["school_id_giga"].isin(counts[counts >= min_tests].index)]
    if keep.empty:
        return pd.DataFrame(columns=["attribute", "value", "schools", "share_pct"])

    rows = []
    for attribute in ("generation", "band"):
        modal = (keep.dropna(subset=[attribute])
                     .groupby("school_id_giga")[attribute]
                     .agg(lambda s: s.value_counts().idxmax()))
        total = len(modal)
        for value, n in modal.value_counts().items():
            rows.append({"attribute": attribute, "value": value, "schools": int(n),
                         "share_pct": round(100 * n / total, 1)})
    return pd.DataFrame(rows)


def wifi_bottleneck(wifi: pd.DataFrame) -> dict:
    """
    Whether the radio, rather than the connection, is what caps the result.

    Where measured throughput sits far below the negotiated rate the radio has
    headroom and the limit is upstream; where it approaches it, the result is a
    floor on the school's connection rather than a measure of it.
    """
    usable = wifi[~wifi["over_phy"]]
    if usable.empty:
        return {}
    return {
        "tests": len(usable),
        "median_radio_rate_mbps": round(float(usable["wifi_tx_rate"].median()), 1),
        "median_measured_mbps": round(float(usable["download_speed"].median()), 1),
        "median_ratio": round(float(usable["phy_ratio"].median()), 2),
        "radio_limited_pct": round(100 * usable["radio_limited"].mean(), 1),
        "excluded_over_phy": int(wifi["over_phy"].sum()),
    }


def wifi_correlations(wifi: pd.DataFrame, min_tests: int = 5) -> pd.DataFrame:
    """
    Spearman rank correlations across schools, one point per school.

    Per school rather than per test: tests within a school share its radio and
    its connection, so pooling them would count the same fact repeatedly and
    shrink the p-values on nothing.
    """
    from scipy import stats

    counts = wifi.groupby("school_id_giga").size()
    keep = wifi[wifi["school_id_giga"].isin(counts[counts >= min_tests].index)]
    if keep.empty:
        return pd.DataFrame()

    per_school = keep.groupby("school_id_giga").agg(
        signal=("wifi_signal", "median"),
        radio_rate=("wifi_tx_rate", "median"),
        throughput=("download_speed", "median"),
        rtt=("latency", "median"),
        loss=("packet_loss_rate", lambda s: pd.to_numeric(s, errors="coerce").median()),
    ).dropna()

    pairs = [("signal", "throughput"), ("signal", "rtt"),
             ("signal", "loss"), ("radio_rate", "throughput")]
    rows = []
    for a, b in pairs:
        if len(per_school) < 3:
            continue
        rho, p = stats.spearmanr(per_school[a].astype(float),
                                 per_school[b].astype(float))
        rows.append({"relationship": f"{a} vs {b}", "rho": round(float(rho), 2),
                     "p": round(float(p), 3), "schools": len(per_school),
                     "significant": bool(p < 0.05)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Cross-country view
# ---------------------------------------------------------------------------

_WIFI_COLUMNS = """
    iso3_code, school_id_giga, measurement_uuid,
    wifi_model, wifi_signal, wifi_tx_rate, wifi_frequency,
    download_speed, latency, packet_loss_rate, detected_location_distance
"""


def fetch_wifi(iso3_codes: list[str], start: str, end: str, cursor=None,
               use_cached: bool = True, cache_name: str = "wifi_all") -> pd.DataFrame:
    """
    Pull every Giga Meter measurement that reported a Wi-Fi link, for several
    countries at once.

    This deliberately does not go through the traceroute join. The Wi-Fi link
    is inside the school and has nothing to do with the path to a test server,
    so restricting to tests that happen to carry a traceroute would discard most
    of the evidence for no gain — for these countries it is the difference
    between roughly 455,000 measurements and a small fraction of them.
    """
    from pathlib import Path
    cache = Path(__file__).resolve().parent.parent / "cache"
    path = cache / f"{cache_name}_{start}_{end}.parquet"
    if use_cached and path.exists():
        return pd.read_parquet(path)

    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    codes = "','".join(sorted(iso3_codes))
    cursor.execute(f"""
        SELECT {_WIFI_COLUMNS}
        FROM all_gigameter_measurement_data
        WHERE iso3_code IN ('{codes}')
          AND date >= DATE '{start}' AND date <= DATE '{end}'
          AND wifi_tx_rate IS NOT NULL
    """)
    frame = pd.DataFrame(cursor.fetchall(),
                         columns=[d[0] for d in cursor.description])
    cache.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


def wifi_country_profiles(wifi_all: pd.DataFrame, min_tests: int = 5,
                          min_schools: int = 5) -> pd.DataFrame:
    """
    One row per country: the estate, the bottleneck, and whether the radio
    explains the result.

    Countries are summarised over schools rather than tests, so a country whose
    measurements concentrate in a few heavily-tested schools is not described by
    those schools. `min_tests` is the per-school threshold to be counted at all;
    `min_schools` is the number of qualifying schools a country needs before its
    correlations are reported, since a rank correlation over three points says
    nothing.
    """
    from scipy import stats

    rows = []
    for iso3, group in wifi_all.groupby("iso3_code"):
        wifi = classify_wifi(group.assign(id=group["measurement_uuid"]))
        counts = wifi.groupby("school_id_giga").size()
        keep = wifi[wifi["school_id_giga"].isin(counts[counts >= min_tests].index)]
        if keep.empty:
            continue

        per_school = keep.groupby("school_id_giga").agg(
            signal=("wifi_signal", "median"),
            radio_rate=("wifi_tx_rate", "median"),
            throughput=("download_speed", "median"),
        ).dropna()

        usable = keep[~keep["over_phy"]]
        estate = wifi_estate(keep, min_tests=min_tests)

        def modal(attribute):
            subset = estate[estate["attribute"] == attribute]
            if subset.empty:
                return None, None
            top = subset.sort_values("schools", ascending=False).iloc[0]
            return top["value"], top["share_pct"]

        generation, generation_share = modal("generation")
        band, band_share = modal("band")

        # Hardware that can use 5 GHz but is observed on 2.4 GHz. This is the
        # difference between what a school owns and what it is configured to
        # use, and it is a settings change rather than a procurement.
        capable = wifi[wifi["generation"].isin(["802.11ac", "802.11ax"])]
        stuck = (capable["band"] == "2.4 GHz").mean() if len(capable) else None

        row = {
            "iso3": iso3,
            "wifi_tests": len(wifi),
            "schools": int(keep["school_id_giga"].nunique()),
            "capable_hw_pct": round(100 * len(capable) / len(wifi), 1) if len(wifi) else None,
            "capable_on_24ghz_pct": round(100 * stuck, 1) if stuck is not None else None,
            "modal_generation": generation, "generation_pct": generation_share,
            "modal_band": band, "band_pct": band_share,
            "median_radio_mbps": round(float(usable["wifi_tx_rate"].median()), 1)
                                 if len(usable) else None,
            "median_measured_mbps": round(float(usable["download_speed"].median()), 1)
                                    if len(usable) else None,
            "median_ratio": round(float(usable["phy_ratio"].median()), 2)
                            if len(usable) else None,
            "radio_limited_pct": round(100 * usable["radio_limited"].mean(), 1)
                                 if len(usable) else None,
            "over_phy_pct": round(100 * wifi["over_phy"].mean(), 1),
        }

        if len(per_school) >= min_schools:
            for label, column in (("signal", "signal"), ("radio", "radio_rate")):
                rho, p = stats.spearmanr(per_school[column].astype(float),
                                         per_school["throughput"].astype(float))
                row[f"rho_{label}_tput"] = round(float(rho), 2)
                row[f"p_{label}_tput"] = round(float(p), 4)
        rows.append(row)

    return pd.DataFrame(rows).sort_values("schools", ascending=False).reset_index(drop=True)


def band_comparison(wifi: pd.DataFrame, min_tests: int = 5) -> pd.DataFrame:
    """
    Compare the two bands *within* each school, one row per school.

    Comparing bands across schools confounds the radio with everything else
    that differs between schools — the connection behind it above all. A school
    seen on both bands is its own control: same connection, same site, same
    equipment, and only the radio changes.

    Returns the per-school medians on each band and their difference, for
    schools with at least `min_tests` on both.
    """
    usable = wifi[wifi["band"].notna() & ~wifi["over_phy"]]
    per = (usable.groupby(["school_id_giga", "band"])
                 .agg(tests=("download_speed", "size"),
                      throughput=("download_speed", "median"),
                      radio_rate=("wifi_tx_rate", "median"),
                      signal=("wifi_signal", "median"))
                 .reset_index())
    per = per[per["tests"] >= min_tests]

    wide = per.pivot(index="school_id_giga", columns="band")
    if not {"2.4 GHz", "5 GHz"}.issubset(set(wide.columns.get_level_values(1))):
        return pd.DataFrame()
    wide = wide.dropna(subset=[("throughput", "2.4 GHz"), ("throughput", "5 GHz")])
    if wide.empty:
        return pd.DataFrame()

    return pd.DataFrame({
        "throughput_24": wide[("throughput", "2.4 GHz")],
        "throughput_5": wide[("throughput", "5 GHz")],
        "throughput_gain": wide[("throughput", "5 GHz")] - wide[("throughput", "2.4 GHz")],
        "radio_gain": wide[("radio_rate", "5 GHz")] - wide[("radio_rate", "2.4 GHz")],
        "signal_delta": wide[("signal", "5 GHz")] - wide[("signal", "2.4 GHz")],
    }).reset_index()


def band_verdict(comparison: pd.DataFrame) -> dict:
    """
    Whether moving a school to 5 GHz reliably helps, and how much of the
    theoretical gain survives.

    `conversion` is the share of the negotiated-rate gain that reaches actual
    throughput. A low value means the radio was never the binding constraint,
    so the band is not what is holding those schools back.
    """
    if comparison.empty:
        return {}
    from scipy import stats
    gain = comparison["throughput_gain"]
    radio = comparison["radio_gain"].median()
    return {
        "schools": len(comparison),
        "median_radio_gain_mbps": round(float(radio), 1),
        "median_throughput_gain_mbps": round(float(gain.median()), 1),
        "conversion_pct": round(100 * float(gain.median()) / float(radio), 1) if radio else None,
        "pct_faster_on_5ghz": round(100 * float((gain > 0).mean()), 1),
        "pct_faster_on_24ghz": round(100 * float((gain < 0).mean()), 1),
        "wilcoxon_p": float(stats.wilcoxon(gain).pvalue) if len(gain) > 10 else None,
    }
