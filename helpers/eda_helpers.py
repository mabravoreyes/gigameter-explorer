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
