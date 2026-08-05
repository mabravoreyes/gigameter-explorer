"""
Analysis helpers for the Giga Meter EDA Explorer — kept out of the notebook so
cells stay thin. Sections: education-level inference, ISP name canonicalisation,
the IQB-Edu scoring engine (faithful port of the `iqb` package), and the legacy
Mbps service-tier scaffolding used by the appendix.
"""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Education level inference (from school name; substring keywords)
# ─────────────────────────────────────────────────────────────────────────────
def infer_edlevel_from_name(name):
    """
    Infer education_level from school name for ALL schools.
    Handles compound levels (e.g., 'Nursery and Primary' → 'Pre-Primary and Primary')
    """
    if pd.isna(name):
        return np.nan
    
    name = str(name).upper().strip()
    
    # Keywords for each level
    primary_keywords = ['PRIMARY', 'BASIC', 'ELEMENTARY', 'PRIM', 'PRI.', '\\bP\\.?\\s*S\\.?\\b']
    secondary_keywords = ['SECONDARY', 'HIGH SCHOOL', 'HIGH', 'GRAMMAR', 'TECHNICAL', 'TECH', 'SEC', '\\bH\\.?\\s*S\\.?\\b', 'COLLEGE']
    preprimary_keywords = ['NURSERY', 'PRE-PRIMARY', 'PRE-SCHOOL', 'ECE', 'PLAYGROUP', 'KINDERGARTEN', 'KINDER', 'PRESCHOOL']
    
    # Check for keywords
    has_primary = any(kw in name for kw in primary_keywords)
    has_secondary = any(kw in name for kw in secondary_keywords)
    has_preprimary = any(kw in name for kw in preprimary_keywords)
    
    # Handle compound levels
    if has_preprimary and has_primary and has_secondary:
        return 'Pre-Primary, Primary and Secondary'
    elif has_preprimary and has_primary:
        return 'Pre-Primary and Primary'
    elif has_primary and has_secondary:
        return 'Primary and Secondary'
    elif has_preprimary and has_secondary:
        return 'Pre-Primary and Secondary'
    elif has_preprimary:
        return 'Pre-Primary'
    elif has_secondary:
        return 'Secondary'
    elif has_primary:
        return 'Primary'
    else:
        return np.nan


# ─────────────────────────────────────────────────────────────────────────────
# ISP name canonicalisation
# Base dict collapses known variants; per-country overrides come from
# isp_mappings.json ({ISO3: {canonical: [patterns...]}}) via build_isp_canon().
# ─────────────────────────────────────────────────────────────────────────────
BASE_ISP_CANON = {          # substring (lowercased, after cleaning) -> canonical name
    "mtel": "MTEL",
    "crnogorski telekom": "Crnogorski Telekom",
    "telenor": "Telenor Montenegro",
    "one crna gora": "One",
    "telemach": "Telemach",
    "viasat": "Viasat",
    "orion": "Orion Telekom",
    "telekomunikacije republike srpske": "m:tel (Telekom Srpske)",
    "telekom srbija": "Telekom Srbija",
}

_ISP_SUFFIX = re.compile(
    r"\b(drustvo za telekomunikacije|akcionarsko drustvo|d\.?o\.?o\.?|doo|dooel|a\.?d\.?|inc|ltd|llc|jsc|gmbh|s\.?a\.?)\b",
    re.IGNORECASE)

def clean_isp(name):
    if pd.isna(name):
        return name
    s = str(name).replace('"', " ").replace("'", " ")   # drop quotes
    s = _ISP_SUFFIX.sub(" ", s)                          # drop legal suffixes
    s = re.sub(r"[.,]", " ", s)                          # drop punctuation
    s = re.sub(r"\s+", " ", s).strip()                   # collapse whitespace
    return s


def build_isp_canon(country_iso3, extra_paths=()):
    """Return (canon_dict, canon_isp_fn, loaded_from) for a country.

    Merges per-country patterns from the first isp_mappings.json found (notebook
    cwd, helpers/, or next to this module) over BASE_ISP_CANON."""
    canon = dict(BASE_ISP_CANON)
    loaded_from = None
    candidates = [Path("isp_mappings.json"), Path("helpers") / "isp_mappings.json",
                  Path(__file__).parent / "isp_mappings.json",
                  Path(__file__).parent.parent / "isp_mappings.json",
                  *[Path(p) for p in extra_paths]]
    for p in candidates:
        if p.exists():
            cmap = json.load(open(p)).get(str(country_iso3).upper(), {})
            for canonical, patterns in cmap.items():
                for pat in patterns:
                    canon[str(pat).lower()] = canonical
            if cmap:
                loaded_from = p
            break

    def canon_isp(name):
        c = clean_isp(name)
        if not isinstance(c, str) or not c:
            return c
        low = c.lower()
        for kw, canonical in canon.items():
            if kw in low:
                return canonical
        return c

    return canon, canon_isp, loaded_from


# ─────────────────────────────────────────────────────────────────────────────
# IQB-Edu scoring engine (verbatim from the notebook / iqb package port)
# ─────────────────────────────────────────────────────────────────────────────
# Mirrors iqb.config.IQB_CONFIG and iqb.calculator.IQBCalculator.calculate_iqb_score
# from the IQB-Edu repo (Delivery/Ad-Hoc/IQB-Edu/2026-04-iqb-edu). M-Lab dataset only.
# Score is continuous 0..1 per use case; computed at multiple percentiles (p50, p95).
import copy

IQB_CONFIG = {
    "use cases": {
        "web browsing": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 3, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 2, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 4, "threshold min": 100,   "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.01,  "datasets": {"m-lab": {"w": 1}}}}},
        "video streaming": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 2, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 4, "threshold min": 100,   "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.01,  "datasets": {"m-lab": {"w": 1}}}}},
        "audio streaming": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 4, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 1, "threshold min": 5,     "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 3, "threshold min": 100,   "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.01,  "datasets": {"m-lab": {"w": 1}}}}},
        "video conferencing": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 4, "threshold min": 50,    "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.005, "datasets": {"m-lab": {"w": 1}}}}},
        "online backup": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 4, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 2, "threshold min": 100,   "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.01,  "datasets": {"m-lab": {"w": 1}}}}},
        "gaming": {"w": 1, "network requirements": {
            "download_throughput_mbps": {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "upload_throughput_mbps":   {"w": 4, "threshold min": 25,    "datasets": {"m-lab": {"w": 1}}},
            "latency_ms":               {"w": 5, "threshold min": 10,    "datasets": {"m-lab": {"w": 1}}},
            "packet_loss":              {"w": 4, "threshold min": 0.005, "datasets": {"m-lab": {"w": 1}}}}},
    }
}
IQB_USE_CASES = list(IQB_CONFIG["use cases"].keys())
IQB_PERCENTILES = [50, 95]          # p50 = typical, p95 = best-throughput / worst-latency tail
IQB_BENCHMARK = 1                 # score >= benchmark -> "ready" for that use case
MIN_MEASUREMENTS_FOR_IQB = 30       # schools below this are excluded from scoring

def _binary_requirement_score(nr, value, threshold):
    # throughput passes when ABOVE threshold; latency/loss pass when BELOW.
    if nr in ("download_throughput_mbps", "upload_throughput_mbps"):
        return 1 if value > threshold else 0
    return 1 if value < threshold else 0

def calculate_iqb_score(data, config=None):
    """Faithful port of IQBCalculator.calculate_iqb_score.
    `data` = {"m-lab": {download_throughput_mbps, upload_throughput_mbps, latency_ms, packet_loss}}.
    Requirements whose value is NaN (e.g. packet loss pending) are skipped, so verdicts
    degrade to the available metrics instead of failing the whole school."""
    config = IQB_CONFIG if config is None else config
    uc_scores, uc_weights = [], []
    for uc, ucfg in config["use cases"].items():
        uc_w = ucfg["w"]
        nr_scores, nr_weights = [], []
        for nr, ncfg in ucfg["network requirements"].items():
            ds_s = []
            for ds, dcfg in ncfg["datasets"].items():
                if dcfg["w"] > 0:
                    val = data[ds][nr]
                    if val is None or pd.isna(val):
                        continue          # metric unavailable -> skip
                    ds_s.append(_binary_requirement_score(nr, val, ncfg["threshold min"]))
            if not ds_s:
                continue                  # requirement unmeasurable -> exclude
            nr_scores.append((sum(ds_s) / len(ds_s)) * ncfg["w"]); nr_weights.append(ncfg["w"])
        if not nr_weights:
            continue
        uc_scores.append((sum(nr_scores) / sum(nr_weights)) * uc_w); uc_weights.append(uc_w)
    return sum(uc_scores) / sum(uc_weights) if sum(uc_weights) else float("nan")

def _config_for_use_case(uc):
    cfg = copy.deepcopy(IQB_CONFIG)
    for u in cfg["use cases"]:
        cfg["use cases"][u]["w"] = 1 if u == uc else 0
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Mbps service-tier scaffolding (appendix cells)
# ─────────────────────────────────────────────────────────────────────────────
TIER_THRESHOLD_1, TIER_THRESHOLD_2, TIER_THRESHOLD_3 = 1, 5, 20
tier_order = ["TIER 0 - Insufficient", "TIER 1 - Basic", "TIER 2 - Ready", "TIER 3 - Advanced"]

def classify_service_level(download_median, upload_median, latency_median, packet_loss_median=None):
    if download_median >= 20 and upload_median >= 10 and latency_median < 50:
        return "TIER 3 - Advanced"
    elif download_median >= 5 and download_median < 20 and upload_median >= 2 and upload_median < 10 and latency_median < 100:
        return "TIER 2 - Ready"
    elif download_median >= 1 and download_median < 5 and upload_median >= 0.5 and upload_median < 2 and latency_median < 150:
        return "TIER 1 - Basic"
    elif download_median >= 5 and upload_median >= 2 and latency_median < 100:
        return "TIER 2 - Ready"
    elif download_median >= 1 and upload_median >= 0.5 and latency_median < 150:
        return "TIER 1 - Basic"
    return "TIER 0 - Insufficient"


# ─────────────────────────────────────────────────────────────────────────────
# Robust group-comparison statistics (peak vs off-peak, ISP, WiFi/Ethernet, …)
#
# Two facts about this data drive every choice here:
#   1. Measurements are NOT independent — one school reports hundreds of them, a
#      busy device thousands. A test run on raw measurement rows commits
#      pseudoreplication and reports wildly overconfident p-values. So we always
#      aggregate to one value per UNIT (usually school) per group first.
#   2. Speeds/latency are heavily right-skewed, so we compare medians with
#      nonparametric tests (Wilcoxon / Mann–Whitney) and quote a bootstrap CI on
#      the effect rather than leaning on a mean-based t-test.
#
# paired_shift_test    — same units measured in BOTH groups (peak vs off-peak).
# two_group_shift_test — units split ACROSS two groups (WiFi vs Ethernet, ISP A/B).
# bootstrap_ci         — CI for any statistic by resampling.
# format_shift_result  — pretty-print either result dict.
# ─────────────────────────────────────────────────────────────────────────────
def bootstrap_ci(values, stat=np.median, n_boot=2000, ci=95, seed=0):
    """Percentile bootstrap CI for `stat` over a 1-D array. Returns (point, lo, hi)."""
    v = np.asarray(pd.Series(values).dropna(), dtype=float)
    if v.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    point = float(stat(v))
    if v.size == 1:
        return (point, point, point)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    boot = stat(v[idx], axis=1)
    lo, hi = np.percentile(boot, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    return (point, float(lo), float(hi))


def _unit_group_medians(df, unit_col, group_col, value_col, groups, min_per_cell):
    """One median per (unit, group) cell, dropping cells thinner than min_per_cell.
    Returns a unit-indexed frame with one column per requested group."""
    sub = df[df[group_col].isin(groups)][[unit_col, group_col, value_col]].dropna(subset=[value_col])
    agg = sub.groupby([unit_col, group_col])[value_col].agg(["median", "count"])
    agg = agg[agg["count"] >= min_per_cell]["median"].unstack(group_col)
    return agg.reindex(columns=list(groups))


def paired_shift_test(df, unit_col, group_col, value_col, group_a, group_b,
                      min_per_cell=3, n_boot=2000, ci=95, seed=0):
    """Paired shift in `value_col` between two groups, matched within `unit_col`.

    Designed for peak vs off-peak: each school is its own control. Aggregates to
    one median per school per period, keeps schools present in BOTH periods with
    at least `min_per_cell` measurements each, then:
      • Wilcoxon signed-rank on the paired medians (nonparametric),
      • matched-pairs rank-biserial effect size,
      • bootstrap CI on the median paired difference (a − b) and median % change.

    Returns a dict (see format_shift_result). `n_pairs == 0` means too little
    overlap to test — caller should report "insufficient paired data".
    """
    from scipy import stats

    wide = _unit_group_medians(df, unit_col, group_col, value_col,
                               (group_a, group_b), min_per_cell).dropna()
    a = wide[group_a].to_numpy(dtype=float)
    b = wide[group_b].to_numpy(dtype=float)
    out = {"test": "wilcoxon-signed-rank", "value": value_col, "unit": unit_col,
           "group_a": group_a, "group_b": group_b, "n_pairs": int(wide.shape[0]),
           "median_a": float("nan"), "median_b": float("nan"),
           "median_diff": float("nan"), "diff_ci": (float("nan"), float("nan")),
           "median_pct": float("nan"), "pct_ci": (float("nan"), float("nan")),
           "statistic": float("nan"), "p_value": float("nan"), "effect": float("nan")}
    if wide.shape[0] == 0:
        return out

    diff = a - b
    out["median_a"] = float(np.median(a))
    out["median_b"] = float(np.median(b))
    out["median_diff"] = float(np.median(diff))
    _, lo, hi = bootstrap_ci(diff, n_boot=n_boot, ci=ci, seed=seed)
    out["diff_ci"] = (lo, hi)

    nz = b != 0
    if nz.any():
        pct = 100.0 * diff[nz] / b[nz]
        p_point, p_lo, p_hi = bootstrap_ci(pct, n_boot=n_boot, ci=ci, seed=seed)
        out["median_pct"], out["pct_ci"] = p_point, (p_lo, p_hi)

    # Wilcoxon needs at least one nonzero difference.
    if np.any(diff != 0):
        try:
            res = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
            out["statistic"], out["p_value"] = float(res.statistic), float(res.pvalue)
        except ValueError:
            pass
        nonzero = diff[diff != 0]
        ranks = stats.rankdata(np.abs(nonzero))
        t_plus = ranks[nonzero > 0].sum()
        t_minus = ranks[nonzero < 0].sum()
        total = t_plus + t_minus
        out["effect"] = float((t_plus - t_minus) / total) if total else 0.0
    else:
        out["p_value"] = 1.0
        out["effect"] = 0.0
    return out


def two_group_shift_test(df, unit_col, group_col, value_col, group_a, group_b,
                         min_per_cell=3, n_boot=2000, ci=95, seed=0):
    """Unpaired shift between two groups whose UNITS differ (WiFi vs Ethernet, ISP A vs B).

    Aggregates to one median per unit within its group (avoiding pseudoreplication),
    then Mann–Whitney U on the per-unit medians, Cliff's delta effect size, and a
    bootstrap CI on the difference in group medians (a − b). A unit contributing to
    both groups appears in each — that is fine; the test stays unpaired.
    """
    from scipy import stats

    wide = _unit_group_medians(df, unit_col, group_col, value_col,
                               (group_a, group_b), min_per_cell)
    a = wide[group_a].dropna().to_numpy(dtype=float)
    b = wide[group_b].dropna().to_numpy(dtype=float)
    out = {"test": "mann-whitney-u", "value": value_col, "unit": unit_col,
           "group_a": group_a, "group_b": group_b,
           "n_a": int(a.size), "n_b": int(b.size),
           "median_a": float("nan"), "median_b": float("nan"),
           "median_diff": float("nan"), "diff_ci": (float("nan"), float("nan")),
           "statistic": float("nan"), "p_value": float("nan"), "effect": float("nan")}
    if a.size == 0 or b.size == 0:
        return out

    out["median_a"], out["median_b"] = float(np.median(a)), float(np.median(b))
    out["median_diff"] = out["median_a"] - out["median_b"]

    rng = np.random.default_rng(seed)
    boot = (np.median(a[rng.integers(0, a.size, (n_boot, a.size))], axis=1)
            - np.median(b[rng.integers(0, b.size, (n_boot, b.size))], axis=1))
    lo, hi = np.percentile(boot, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    out["diff_ci"] = (float(lo), float(hi))

    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    out["statistic"], out["p_value"] = float(u), float(p)
    out["effect"] = float(2.0 * u / (a.size * b.size) - 1.0)   # Cliff's delta
    return out


def format_shift_result(res, label=None, better="up", alpha=0.05):
    """Render a paired_shift_test / two_group_shift_test dict as a readable block.
    `better`: 'up' if higher `value` is better (speed), 'down' if lower is (latency)."""
    label = label or f"{res['value']} ({res['group_a']} vs {res['group_b']})"
    n = res.get("n_pairs", None)
    lines = [f"{label}:"]
    if n is not None:
        if n == 0:
            return "\n".join(lines + ["  insufficient paired data (no unit measured in both groups)"])
        lines.append(f"  paired on {n} {res['unit']}s | "
                     f"median {res['group_a']}={res['median_a']:.2f}, {res['group_b']}={res['median_b']:.2f}")
    else:
        if res["n_a"] == 0 or res["n_b"] == 0:
            return "\n".join(lines + ["  insufficient data in one group"])
        lines.append(f"  {res['group_a']} n={res['n_a']}, {res['group_b']}={res['n_b']} {res['unit']}s | "
                     f"median {res['median_a']:.2f} vs {res['median_b']:.2f}")

    dlo, dhi = res["diff_ci"]
    lines.append(f"  median shift (a−b): {res['median_diff']:+.2f}  95% CI [{dlo:+.2f}, {dhi:+.2f}]")
    if res.get("median_pct") == res.get("median_pct") and "median_pct" in res:  # not NaN
        plo, phi = res["pct_ci"]
        lines.append(f"  median % change:    {res['median_pct']:+.1f}%  95% CI [{plo:+.1f}%, {phi:+.1f}%]")
    lines.append(f"  {res['test']}: p={res['p_value']:.4f} | effect={res['effect']:+.3f}")

    p = res["p_value"]
    if p != p:  # NaN
        verdict = "no test (degenerate input)"
    elif p < alpha:
        # CI excludes 0 → direction is trustworthy
        direction = "higher" if res["median_diff"] > 0 else "lower"
        note = "" if better == "up" else "  (lower is better here)"
        verdict = f"✓ significant (p<{alpha}) — {res['group_a']} is {direction}{note}"
    else:
        verdict = f"✗ not significant (p≥{alpha}) — shift within noise"
    lines.append(f"  → {verdict}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Country resolution — one code in, everything else out
# ─────────────────────────────────────────────────────────────────────────────
def _load_country_reference():
    for p in (Path(__file__).parent / "country_reference.json",
              Path("country_reference.json"),
              Path("helpers") / "country_reference.json"):
        if p.exists():
            return json.load(open(p))
    raise FileNotFoundError("country_reference.json not found next to eda_helpers.py")


def resolve_country(code, timezone=None):
    """Resolve an ISO3 code (or country name) -> dict(iso3, iso2, name, timezone, timezones).

    Timezone pick order: explicit `timezone` arg > the single pytz zone when the
    country has exactly one > the curated registry default for multi-zone countries."""
    import pytz
    ref = _load_country_reference()
    code_s = str(code).strip()
    iso3 = None
    if len(code_s) == 3 and code_s.upper() in ref:
        iso3 = code_s.upper()
    else:
        for k, v in ref.items():
            if v.get("name", "").lower() == code_s.lower():
                iso3 = k
                break
    if iso3 is None:
        raise KeyError(f"{code!r} not found in country_reference.json — add an entry or pass its ISO3")
    entry = ref[iso3]
    iso2, name = entry["iso2"], entry["name"]
    zones = pytz.country_timezones.get(iso2, [])
    tz = timezone or (zones[0] if len(zones) == 1 else entry.get("timezone"))
    if not tz:
        raise ValueError(f"{name} spans {len(zones)} timezones {zones} — pass timezone=...")
    return {"iso3": iso3, "iso2": iso2, "name": name, "timezone": tz, "timezones": zones}
