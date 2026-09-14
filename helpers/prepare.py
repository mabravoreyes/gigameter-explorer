"""
prepare.py — the ONE shared load + clean pipeline behind the numbered notebooks.

download_data_01 and meter_explorer_02 used to carry their own copies of this
sequence (and meter_explorer's copy silently skipped the latency-cutoff choice).
This module is now the single source of truth. Flow:

    from prepare import load_country, latency_distribution, prepare_country

    L = load_country("ZAF", use_cached=True)     # raw load — nothing dropped yet
    latency_distribution(L.m)                    # inspect, THEN choose a cutoff
    P = prepare_country(L, latency_cutoff="p99", admin1="Eastern Cape")

    m, m_original, funnel = P.m, P.m_original, P.filter_log

Two design rules:
  1. VISIBILITY — every row that leaves the analysis is counted in
     P.filter_log and printed as a funnel; value-level cleaning (impossible
     speeds/latency nulled, rows kept) is reported separately in
     P.values_nulled. Nothing is dropped silently.
  2. THE LATENCY CUTOFF IS A CHOICE, NOT A DEFAULT — call
     latency_distribution() first and pass a number, or a named rule
     ('p95' | 'p99' | 'p99.5' | 'iqr' | 'modz'). 'p99' is the conventional
     default, kept explicit in the call site so it shows up in review.
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from eda_helpers import resolve_country
from load_measurements import load_measurements, get_trino_cursor
from load_master import load_master

# uint32-microseconds overflow sentinel — not a measurement
LATENCY_SENTINEL_MS = 4_294_967

_WIFI_NUMERIC = ["wifi_quality", "wifi_signal", "wifi_tx_rate",
                 "wifi_channel", "wifi_frequency"]
_MASTER_WANTED = ["education_level", "education_level_govt", "connectivity_provider",
                  "admin1", "admin2", "connectivity_type_govt", "latitude", "longitude"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD — raw pull, nothing dropped
# ─────────────────────────────────────────────────────────────────────────────
def load_country(country, use_cached=True, cur=None,
                 measurement_source=None, rowlevel_window_days=None,
                 load_columns=None, cache_root="./cache", registration=True):
    """Load master + measurements (+ registration) for one country.

    Returns a namespace: .m (raw measurements, field-prepped only), .master,
    .registration, .iso3/.iso2/.name/.tz, .cache_dir, .filter_log ({'loaded': n}),
    .cur. No rows are dropped here — cleaning happens in prepare_country().
    """
    c = resolve_country(country)
    iso3, iso2, name, tz = c["iso3"], c["iso2"], c["name"], c["timezone"]
    cache_dir = Path(cache_root) / name
    cache_dir.mkdir(parents=True, exist_ok=True)
    slug = name.lower().replace(" ", "")

    if not use_cached and cur is None:
        cur = get_trino_cursor()          # auto-starts the port-forward

    master = load_master(iso3, cache_dir / f"{iso3}_master_datapull.csv",
                         use_cached=use_cached)

    m = load_measurements(name, cache_dir / f"{slug}_measurements.parquet", cur,
                          use_cached=use_cached, source=measurement_source,
                          columns=load_columns, window_days=rowlevel_window_days)

    # Schema compatibility — the consolidated table's column set varies by source.
    # GigaMeter rows use created_timestamp / isp_name / packet_loss_rate; legacy
    # DailyCheckApp rows carry timestamp / detected_isp. Alias to the legacy
    # names downstream cells expect, then build the tz-aware timestamplocal.
    if "timestamp" not in m.columns and "created_timestamp" in m.columns:
        m["timestamp"] = m["created_timestamp"]
    if "detected_isp" not in m.columns and "isp_name" in m.columns:
        m["detected_isp"] = m["isp_name"]
    if "detected_isp_asn" not in m.columns and "isp_asn" in m.columns:
        m["detected_isp_asn"] = m["isp_asn"]
    if "date" in m.columns:
        m["date"] = pd.to_datetime(m["date"])
    m["timestamp"] = pd.to_datetime(m["timestamp"], utc=True)
    m["timestamplocal"] = m["timestamp"].dt.tz_convert(tz)

    # registration (one row per school, funnel metadata) — cached parquet
    reg = None
    if registration:
        reg_path = cache_dir / f"{slug}_registered.parquet"
        if use_cached and reg_path.exists():
            reg = pd.read_parquet(reg_path)
        elif cur is not None:
            cur.execute(f"""
                SELECT *
                FROM default.all_gigameter_registered_schools
                WHERE iso3_code = '{iso3.upper()}'
            """)
            reg = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
            reg.to_parquet(reg_path, index=False)
        else:
            print(f"ℹ registration skipped — no cache at {reg_path.name} and no cursor")

    # field prep (dtype coercion only — not cleaning)
    for col in _WIFI_NUMERIC:
        if col in m.columns:
            m[col] = pd.to_numeric(m[col], errors="coerce")
    if "packet_loss_rate" in m.columns:
        m["loss_rate"] = pd.to_numeric(m["packet_loss_rate"], errors="coerce")

    print(f"✓ {name} ({iso3}) loaded: {len(m):,} measurements · "
          f"{m['school_id_giga'].nunique():,} schools · master {len(master):,} rows"
          + (f" · registration {len(reg):,}" if reg is not None else ""))

    return SimpleNamespace(iso3=iso3, iso2=iso2, name=name, tz=tz,
                           cache_dir=cache_dir, slug=slug,
                           m=m, master=master, registration=reg,
                           filter_log={"loaded": len(m)}, cur=cur)


# ─────────────────────────────────────────────────────────────────────────────
# 2. INSPECT — the latency distribution, so the cutoff is a decision
# ─────────────────────────────────────────────────────────────────────────────
def latency_cutoff_candidates(latency):
    """Candidate latency-outlier cutoffs (ms) + the share each would exclude."""
    lat = pd.to_numeric(pd.Series(latency), errors="coerce").dropna()
    lat = lat[(lat >= 0) & (lat < LATENCY_SENTINEL_MS)]
    q1, q3 = lat.quantile(0.25), lat.quantile(0.75)
    mad = (lat - lat.median()).abs().median()
    cand = {
        "p95":   lat.quantile(0.95),
        "p99":   lat.quantile(0.99),
        "p99.5": lat.quantile(0.995),
        "iqr":   q3 + 1.5 * (q3 - q1),                       # Q3 + 1.5×IQR
        "modz":  lat.median() + 3.5 * mad / 0.6745,          # modified z-score
        "fixed400":  400.0,
        "fixed1000": 1000.0,
    }
    return pd.DataFrame(
        {"cutoff_ms": {k: round(float(v)) for k, v in cand.items()},
         "excluded_pct": {k: round(100 * float((lat > v).mean()), 2)
                          for k, v in cand.items()}}
    )


def latency_distribution(m, plot=True, country_name=""):
    """Show the latency distribution + candidate cutoffs; returns the candidates.

    Call this BEFORE prepare_country() and pick the cutoff from what you see —
    the point is that the choice is reviewed, not inherited.
    """
    lat = pd.to_numeric(m["latency"], errors="coerce").dropna()
    lat = lat[(lat >= 0) & (lat < LATENCY_SENTINEL_MS)]
    cand = latency_cutoff_candidates(lat)
    if plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 3.5))
        show = lat[lat <= lat.quantile(0.999)]
        ax.hist(show, bins=120, alpha=0.85)
        for name, row in cand.iterrows():
            if row["cutoff_ms"] <= show.max():
                ax.axvline(row["cutoff_ms"], linestyle="--", linewidth=1.2,
                           label=f"{name}: {row['cutoff_ms']:.0f} ms")
        ax.set_yscale("log")
        ax.set_xlabel("Latency (ms; display clipped at p99.9)")
        ax.set_ylabel("measurements (log)")
        ax.set_title(f"Latency distribution — pick the outlier cutoff {country_name}".rstrip())
        ax.legend(fontsize=8, ncol=4)
        plt.tight_layout(); plt.show()
    print("Candidate cutoffs and the share of measurements each would exclude:")
    print(cand.to_string())
    return cand


def _resolve_latency_cutoff(m, latency_cutoff):
    if isinstance(latency_cutoff, (int, float)) and not isinstance(latency_cutoff, bool):
        return float(latency_cutoff), str(latency_cutoff)
    cand = latency_cutoff_candidates(m["latency"])
    key = str(latency_cutoff).lower()
    if key not in cand.index:
        raise ValueError(f"latency_cutoff must be a number or one of {list(cand.index)}")
    return float(cand.loc[key, "cutoff_ms"]), key


def _server_label_canon(series):
    """Map detected_server label variants of the same site onto one canonical
    spelling — labels where one is a word-prefix of the other ('Cape' /
    'Cape Town') are merged, keeping the more frequent spelling. Returns a
    {variant: canonical} dict; empty when there is nothing to merge."""
    counts = series.dropna().astype(str).str.strip().value_counts()
    labels = sorted(counts.index, key=len)
    mapping = {}
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            if b.lower().startswith(a.lower() + " "):
                keep, drop = (a, b) if counts[a] >= counts[b] else (b, a)
                mapping[drop] = keep
    # resolve chains (a→b, b→c ⇒ a→c)
    for k in list(mapping):
        while mapping[k] in mapping:
            mapping[k] = mapping[mapping[k]]
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 3. PREPARE — clean with a visible funnel
# ─────────────────────────────────────────────────────────────────────────────
def prepare_country(loaded, latency_cutoff="p99", server_filter=True,
                    server_pct=0.30, admin1=None, school_hours=(7, 16),
                    verbose=True):
    """Apply the standard cleaning sequence to a load_country() result.

    Row-dropping steps (each counted in .filter_log): dominant-server filter,
    future-dated rows, admin1 scope, latency outliers. Value-level cleaning
    (impossible values → NaN, rows kept) is reported in .values_nulled.

    Returns a namespace: .m (analysis frame), .m_original (clean, unfiltered —
    the drop-off/time-series base), .filter_log, .values_nulled,
    .latency_threshold_ms, .main_servers, .params — plus the loaded country
    metadata passed through.
    """
    L = loaded
    m = L.m.copy()
    log = dict(L.filter_log)          # {'loaded': n}
    nulled = {}

    # ── dominant measurement server(s) — mixing servers mixes baseline latency.
    #    detected_server labels drift (stale mlab-ns endpoint): the same site can
    #    appear as e.g. 'Cape' AND 'Cape Town', splitting its share below the
    #    dominance bar. Merge word-prefix variants BEFORE computing dominance;
    #    the raw detected_server column itself is never modified.
    main_servers = []
    if server_filter and "detected_server" in m.columns:
        canon_map = _server_label_canon(m["detected_server"])
        srv_canon = m["detected_server"].map(lambda x: canon_map.get(x, x))
        counts = srv_canon.value_counts()                  # non-null only
        frac = counts / counts.sum() if counts.sum() else counts
        main_servers = frac[frac >= server_pct].index.tolist()
        if main_servers:
            before = len(m)
            m = m[srv_canon.isin(main_servers) | srv_canon.isna()]
            log["other_servers"] = before - len(m)
            merged = {v: k for v, k in canon_map.items() if k in main_servers}
            if merged and verbose:
                print("  server label variants merged: "
                      + ", ".join(f"'{v}' → '{k}'" for v, k in merged.items()))
        else:
            log["other_servers"] = 0
    else:
        log["other_servers"] = 0

    # ── future-dated rows (year-2247-style corruption) — dropped
    before = len(m)
    tomorrow = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).normalize()
    ts_utc = pd.to_datetime(m["timestamplocal"], errors="coerce")
    ts_utc = ts_utc.dt.tz_convert("UTC") if ts_utc.dt.tz is not None else ts_utc.dt.tz_localize("UTC")
    m = m[ts_utc < tomorrow]
    log["future_dated"] = before - len(m)

    # ── physical validity — impossible VALUES nulled, rows kept
    for col in ["download_speed", "upload_speed", "latency"]:
        if col in m.columns:
            v = pd.to_numeric(m[col], errors="coerce")
            bad = v < 0
            if col == "latency":
                bad |= v >= LATENCY_SENTINEL_MS
            nulled[col] = int(bad.sum())
            m[col] = v.mask(bad)

    # ── master metadata (only columns m doesn't already carry)
    merge_cols = ["school_id_giga"] + [c for c in _MASTER_WANTED
                                       if c in L.master.columns and c not in m.columns]
    if len(merge_cols) > 1:
        m = m.merge(L.master[merge_cols], on="school_id_giga", how="left")

    # ── snapshot: clean but UNFILTERED — drop-off / time-series analyses use this
    m_original = m.copy()

    # ── convenience time columns
    m["measurement_date"] = pd.to_datetime(m["timestamplocal"]).dt.date
    m["measurement_weekday"] = pd.to_datetime(m["timestamplocal"]).dt.weekday

    # ── resolve the latency cutoff BEFORE any admin scoping, so a named rule
    #    ('p99', …) is computed on the same distribution download_data_01 used
    threshold_ms, rule = _resolve_latency_cutoff(m, latency_cutoff)

    # ── admin1 scope
    before = len(m)
    if admin1:
        m = m[m["admin1"] == admin1]
    log["admin1_filter"] = before - len(m)

    # ── latency outliers (cutoff chosen via latency_distribution; NaN kept —
    #    a row without latency still carries a valid speed test)
    before = len(m)
    m = m[(m["latency"] < threshold_ms) | m["latency"].isna()]
    log["latency_outliers"] = before - len(m)

    # ── school-hours classification (inclusive bounds, as in download_data_01)
    start, end = school_hours
    hours = pd.to_datetime(m["timestamplocal"]).dt.hour
    m["measurement_time_window"] = np.where(
        (hours >= start) & (hours <= end), "school_hours", "off_hours")

    params = {"server_filter": bool(server_filter), "server_pct_threshold": server_pct,
              "main_servers": [str(s) for s in main_servers],
              "latency_outlier_threshold_ms": threshold_ms, "latency_cutoff_rule": rule,
              "admin1_filter": admin1,
              "school_hours_start": start, "school_hours_end": end}

    if verbose:
        print_funnel(log, len(m), values_nulled=nulled)
        print(f"  latency cutoff: {threshold_ms:.0f} ms ({rule})"
              + (f" · servers kept: {main_servers}" if main_servers else "")
              + (f" · admin1: {admin1}" if admin1 else ""))

    return SimpleNamespace(m=m, m_original=m_original, filter_log=log,
                           values_nulled=nulled, latency_threshold_ms=threshold_ms,
                           main_servers=main_servers, params=params,
                           iso3=L.iso3, iso2=L.iso2, name=L.name, tz=L.tz,
                           cache_dir=L.cache_dir, slug=L.slug,
                           master=L.master, registration=L.registration)


def print_funnel(filter_log, final_n, values_nulled=None):
    """Render the row-drop funnel — the visibility contract of this module."""
    loaded = filter_log["loaded"]
    print("=" * 64)
    print("MEASUREMENTS FILTERED OUT OF THE ANALYSIS")
    print("=" * 64)
    print(f"  {'Loaded from cache/Trino':32s} {loaded:>10,}")
    for k, v in filter_log.items():
        if k == "loaded":
            continue
        print(f"  − {k.replace('_', ' '):30s} {v:>10,}   ({100 * v / loaded:.2f}%)")
    print("-" * 64)
    print(f"  {'ANALYSED':32s} {final_n:>10,}   ({100 * final_n / loaded:.1f}% of loaded; "
          f"{loaded - final_n:,} rows removed)")
    if values_nulled:
        kept = ", ".join(f"{k} {v:,}" for k, v in values_nulled.items() if v)
        if kept:
            print(f"  (values nulled, rows kept: {kept})")


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPORT — analysis-ready artefacts for downstream notebooks / Superset
# ─────────────────────────────────────────────────────────────────────────────
def export_clean(prep, extra_params=None):
    """Write {slug}_clean.parquet, {slug}_clean_unfiltered.parquet and the
    params/funnel json into the country cache dir. Returns the three paths."""
    import json
    from datetime import datetime

    clean = prep.cache_dir / f"{prep.slug}_clean.parquet"
    unfilt = prep.cache_dir / f"{prep.slug}_clean_unfiltered.parquet"
    pjson = prep.cache_dir / f"{prep.slug}_clean_params.json"

    prep.m.to_parquet(clean, index=False)
    prep.m_original.to_parquet(unfilt, index=False)

    params = {
        "country": {"iso3": prep.iso3, "iso2": prep.iso2, "name": prep.name,
                    "timezone": prep.tz},
        "filters": prep.params,
        "filter_funnel": {k: int(v) for k, v in prep.filter_log.items()},
        "values_nulled": {k: int(v) for k, v in prep.values_nulled.items()},
        "rows": {"analysed": int(len(prep.m)), "unfiltered": int(len(prep.m_original)),
                 "schools": int(prep.m["school_id_giga"].nunique())},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if extra_params:
        params.update(extra_params)
    pjson.write_text(json.dumps(params, indent=2))

    print(f"✓ {clean.name}  {len(prep.m):,} rows ({clean.stat().st_size/1e6:.1f} MB)")
    print(f"✓ {unfilt.name}  {len(prep.m_original):,} rows")
    print(f"✓ {pjson.name}")
    return clean, unfilt, pjson
