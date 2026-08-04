"""
Measurement data loading and incremental refresh from Trino.

Single source of truth for getting country measurement data into a parquet.
Notebooks should use load_measurements() rather than embedding query logic.

Usage — from a notebook:
    import sys
    sys.path.insert(0, str(Path.home() / 'Documents/Giga/Delivery/Ingestion/Set-Up'))
    from load_measurements import load_measurements, get_trino_cursor, get_trino_engine

    # Requires: kubectl port-forward svc/trino 8080:8080 -n ictd-ooi-trino-prd
    cur    = get_trino_cursor()   # DB-API cursor for refresh_country / load_measurements
    engine = get_trino_engine()   # SQLAlchemy engine for pd.read_sql ad-hoc queries
    m = load_measurements(COUNTRY_NAME, measurements_cache, cur, use_cached=USE_CACHED_DATA)

Usage — from the command line (~10 min per country):
    python refresh_measurements.py MWI LKA
    python refresh_measurements.py --all        # all countries in country_reference.json
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

import format_measurements

# PRD Trino — same params as trino_starter.ipynb.
_TRINO_PRD = dict(
    host="localhost",
    port=8080,
    user="giga-trino",
    catalog="delta_lake",
    schema="default",
    http_scheme="http",
)

_KUBECTL_NAMESPACE = "ictd-ooi-trino-prd"
_KUBECTL_SERVICE   = "svc/trino"
_PORT_FORWARD_WAIT = 4  # seconds to wait after launching before testing


def _port_open(host: str = "localhost", port: int = 8080, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_port_forward() -> bool:
    """
    Start kubectl port-forward in the background if port 8080 is not already open.
    Returns True if the port is reachable after the attempt.

    Requires:
      - kubectl configured for uni-ooi-giga-aks-prd
      - kubelogin convert-kubeconfig -l azurecli already run
      - az login / token still valid (run `az account show` to check)
    """
    if _port_open():
        return True

    print("⏳ Trino port-forward not detected — starting kubectl port-forward...")
    subprocess.Popen(
        ["kubectl", "port-forward", _KUBECTL_SERVICE, "8080:8080", "-n", _KUBECTL_NAMESPACE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(_PORT_FORWARD_WAIT)

    if _port_open():
        print("✓ Port-forward running (localhost:8080)")
        return True

    print(
        "⚠️  Port-forward failed to start. Check:\n"
        "  1. az login  (token expired?)\n"
        "  2. az aks get-credentials --name uni-ooi-giga-aks-prd "
        "--resource-group RS-UNI-GIGA-AKS-PRD\n"
        "  3. kubelogin convert-kubeconfig -l azurecli\n"
        "Then retry, or run manually:\n"
        f"  kubectl port-forward {_KUBECTL_SERVICE} 8080:8080 -n {_KUBECTL_NAMESPACE}"
    )
    return False


def get_trino_engine():
    """
    SQLAlchemy engine for PRD Trino — use with pd.read_sql for ad-hoc queries.
    Matches the `engine` object in trino_starter.ipynb. Auto-starts port-forward.
    """
    _ensure_port_forward()
    try:
        from sqlalchemy import create_engine
        return create_engine(
            f"trino://{_TRINO_PRD['user']}@{_TRINO_PRD['host']}:{_TRINO_PRD['port']}"
            f"/{_TRINO_PRD['catalog']}/{_TRINO_PRD['schema']}"
        )
    except Exception as e:
        print(f"⚠️  Trino engine creation failed: {e}")
        return None


def get_trino_cursor(credentials_dir: Path | None = None, profile: str = "trino_prd"):
    """
    Open a Trino DB-API cursor for PRD. Auto-starts kubectl port-forward if needed.

    Args:
        credentials_dir: unused (kept for backward compat).
        profile:         unused (kept for backward compat).

    Returns:
        Trino cursor, or None if connection fails.
    """
    _ensure_port_forward()
    try:
        from trino.dbapi import connect
    except ImportError:
        print("⚠️  trino not installed — pip install trino")
        return None

    try:
        conn = connect(**_TRINO_PRD)
        cur = conn.cursor()
        print("✓ Trino PRD cursor ready")
        return cur
    except Exception as e:
        print(f"⚠️  Trino connection failed: {e}")
        return None


STREAM_THRESHOLD = 1_000_000  # rows; above this, pulls stream to parquet instead of loading into RAM


def _coercion_spec(description):
    """Map Trino DB-API column types to deterministic pandas dtypes so streamed
    batches always produce the same arrow schema (an all-null early batch would
    otherwise lock the parquet writer to a `null` column type)."""
    spec = {}
    for d in description:
        name, t = d[0], str(d[1]).lower()
        if t.startswith(("varchar", "char", "json")):
            spec[name] = "string"
        elif t.startswith(("bigint", "integer", "smallint", "tinyint")):
            spec[name] = "Int64"
        elif t.startswith(("double", "real", "decimal", "float")):
            spec[name] = "float64"
        elif t.startswith("boolean"):
            spec[name] = "boolean"
        elif "timestamp" in t or t.startswith("date"):
            spec[name] = "datetime_tz" if "with time zone" in t else "datetime"
        else:
            spec[name] = "string"
    return spec


def _coerce_batch(df, spec):
    for c, kind in spec.items():
        if c not in df.columns:
            continue
        if kind == "float64":
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        elif kind == "Int64":
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        elif kind == "boolean":
            df[c] = df[c].map({True: True, False: False}).astype("boolean")
        elif kind == "datetime_tz":
            df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
        elif kind == "datetime":
            df[c] = pd.to_datetime(df[c], utc=False, errors="coerce")
        else:
            df[c] = df[c].astype("string")
    return df


def _stream_query_to_parquet(cur, query, path, append_from=None, batch_size=50_000, label=""):
    """Stream a Trino query to `path` in fetchmany batches (bounded memory).
    If `append_from` is an existing parquet, its row groups are copied through
    afterwards (cast to the new schema). Writes to a temp file, then replaces."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    cur.execute(query)
    spec = _coercion_spec(cur.description)
    cols = [d[0] for d in cur.description]
    tmp = path.with_name(path.name + ".tmp")
    writer, total = None, 0
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        tbl = pa.Table.from_pandas(
            _coerce_batch(pd.DataFrame(rows, columns=cols), spec), preserve_index=False
        )
        if writer is None:
            writer = pq.ParquetWriter(tmp, tbl.schema)
        else:
            tbl = tbl.cast(writer.schema, safe=False)
        writer.write_table(tbl)
        total += len(rows)
        print(f"    {label}streamed {total:,} rows...", end="\r")
    print()
    if writer is None:
        return 0
    if append_from is not None and Path(append_from).exists():
        pf = pq.ParquetFile(append_from)
        for g in range(pf.num_row_groups):
            old = pf.read_row_group(g)
            writer.write_table(old.cast(writer.schema, safe=False))
            total += old.num_rows
    writer.close()
    tmp.replace(path)
    return total


def _parquet_max_date(path):
    """Max date + row count of an existing parquet WITHOUT loading the full file
    (reads only the date column + metadata — matters for multi-million-row files)."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    n_rows = pf.metadata.num_rows
    date_col = next((c for c in ["date", "created_at", "timestamp"] if c in pf.schema_arrow.names), None)
    if date_col is None or n_rows == 0:
        return None, None, n_rows
    col = pq.read_table(path, columns=[date_col])[date_col]
    return date_col, pd.to_datetime(pd.Series(col.to_pandas())).max().date(), n_rows


def refresh_country(
    iso3: str,
    path: Path | str,
    cur,
    country_name: str,
    source: str = None,
    stream_threshold: int = None,
) -> bool:
    """
    Incremental pull for one country: queries delta since max date in parquet.

    Scale-aware (2026-08): the delta is counted first; when new+existing rows
    exceed `stream_threshold` (default STREAM_THRESHOLD = 1M), the pull streams
    to parquet in batches with a deterministic schema instead of loading
    everything into RAM — so the same helper serves Fiji and Uzbekistan alike.
    The streamed path skips the measurement_id dedup; `since` is exclusive
    (date > max cached date), so overlap duplicates cannot occur.

    Args:
        iso3:         ISO3 country code (used for logging only).
        path:         Path to the country measurements parquet.
        cur:          Active Trino cursor (from get_trino_cursor()).
        country_name: Full country name as stored in Trino (e.g. 'Sri Lanka').
        source:       `rt_source` filter (e.g. 'GigaMeter'), or list, or None for
                      all sources. Default None — the consolidated physical table
                      includes all sources in one place.
        stream_threshold: row count above which the streaming path is used.

    Returns:
        True if parquet was updated, False if already up to date or skipped.
    """
    if cur is None:
        print(f"  {iso3}: no DB connection — skipped")
        return False

    path = Path(path)
    if stream_threshold is None:
        stream_threshold = STREAM_THRESHOLD

    since, date_col, n_existing = None, None, 0
    if path.exists():
        date_col, since, n_existing = _parquet_max_date(path)
        if since is not None:
            print(f"  {iso3}: existing data through {since} ({n_existing:,} rows), querying delta...")
        else:
            print(f"  {iso3}: no date column found, doing full pull...")
    else:
        print(f"  {iso3}: no existing parquet, doing full pull...")

    query = format_measurements.get_gigameter_measurements_query(
        country=country_name, source=source, since=since
    )

    cur.execute(f"SELECT count(*) FROM ({query}) t")
    n_new = cur.fetchall()[0][0]
    if n_new == 0:
        print(f"  {iso3}: already up to date")
        return False
    print(f"  {iso3}: {n_new:,} new rows to fetch")

    path.parent.mkdir(parents=True, exist_ok=True)

    if n_new + n_existing > stream_threshold:
        total = _stream_query_to_parquet(cur, query, path, append_from=path if n_existing else None,
                                         label=f"{iso3}: ")
        print(f"  {iso3}: saved {total:,} total rows (streamed)")
        return True

    # In-memory path (small/medium countries) — unchanged behaviour incl. dedup.
    existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    cur.execute(query)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    delta = pd.DataFrame(rows, columns=cols)
    print(f"  {iso3}: {len(delta):,} new rows fetched")

    combined = pd.concat([existing, delta], ignore_index=True)
    if "measurement_id" in combined.columns:
        combined = combined.drop_duplicates("measurement_id")

    # Normalise date-like columns so pyarrow doesn't choke on mixed date/datetime types
    for col in ["date", "created_at", "timestamp", "timestamplocal"]:
        if col in combined.columns:
            combined[col] = pd.to_datetime(combined[col], utc=False, errors="coerce")

    combined.to_parquet(path, index=False)

    ref_col = date_col or "date"
    new_max = pd.to_datetime(combined[ref_col]).max().date() if ref_col in combined.columns else "?"
    print(f"  {iso3}: saved {len(combined):,} total rows, data through {new_max}")
    return True


def _read_parquet_scoped(path, columns=None, window_days=None):
    """Read a measurements parquet with optional column pruning and a trailing
    date window (predicate pushdown — big-country parquets never fully load)."""
    kwargs = {}
    if columns is not None:
        kwargs["columns"] = list(columns)
    if window_days is not None:
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=window_days)
        try:
            return pd.read_parquet(path, filters=[("date", ">=", cutoff)], **kwargs)
        except Exception:  # date column absent/odd type — fall back to full read + filter
            m = pd.read_parquet(path, **kwargs)
            if "date" in m.columns:
                m = m[pd.to_datetime(m["date"], errors="coerce") >= cutoff]
            return m
    return pd.read_parquet(path, **kwargs)


def load_measurements(
    country_name: str,
    path: Path | str,
    cur,
    use_cached: bool = True,
    source: str = None,
    columns: list = None,
    window_days: int = None,
) -> pd.DataFrame:
    """
    Load measurements for a country, refreshing from Trino if needed.

    Behaviour:
      - use_cached=True  + parquet exists  → load from disk, no query.
      - use_cached=False + cur available   → incremental pull (delta only),
                                             save updated parquet, load from disk.
      - use_cached=False + cur is None     → raises FileNotFoundError.
      - parquet missing  regardless        → raises FileNotFoundError.

    Args:
        country_name: Full country name as stored in Trino (e.g. 'Sri Lanka').
        path:         Path to the country measurements parquet.
        cur:          Active Trino cursor, or None for cached-only mode.
        use_cached:   If True, skip Trino and load from existing parquet.
        source:       Measurement source passed to Trino query.
        columns:      Optional column subset to LOAD (the parquet on disk always
                      keeps every column — this only prunes the read).
        window_days:  Optional trailing window to LOAD (e.g. 90). The parquet on
                      disk always keeps full history — this only filters the read.
                      Use for very large countries where the full frame won't fit
                      comfortably in RAM.

    Returns:
        DataFrame of measurements.
    """
    path = Path(path)

    if use_cached:
        if not path.exists():
            raise FileNotFoundError(
                f"Measurements not available and USE_CACHED_DATA=True. "
                f"Provide {path} or set USE_CACHED_DATA=False with a Trino connection."
            )
        m = _read_parquet_scoped(path, columns, window_days)
        print(f"✓ Measurements loaded from cache: {m.shape[0]:,} rows  ({path.name})")
        return m

    # use_cached=False — refresh then load
    if cur is None:
        raise FileNotFoundError(
            f"USE_CACHED_DATA=False but no Trino connection. "
            f"Call get_trino_cursor() first, or set USE_CACHED_DATA=True if {path.name} exists."
        )

    # iso3 is just for log labels — derive a short label from path name
    _label = path.stem
    refresh_country(_label, path, cur, country_name, source=source)

    if not path.exists():
        raise FileNotFoundError(f"Refresh ran but {path} was not created.")

    m = _read_parquet_scoped(path, columns, window_days)
    print(f"✓ Measurements loaded: {m.shape[0]:,} rows  ({path.name})")
    return m


def load_registration(
    country_iso3: str,
    path: Path | str,
    cur,
    use_cached: bool = True,
) -> pd.DataFrame:
    """
    Load registered-school data for a country from the consolidated physical table
    `delta_lake.default.all_gigameter_registered_schools`.

    Behaviour:
      - use_cached=True  + parquet exists  → load from disk, no query.
      - use_cached=False + cur available   → full pull, overwrite parquet.
      - use_cached=False + cur is None     → raises FileNotFoundError.
      - parquet missing  regardless        → raises FileNotFoundError.

    Args:
        country_iso3: ISO3 country code as stored in Trino (e.g. 'MNG', 'LKA').
        path:         Path to the country registration parquet.
        cur:          Active Trino cursor, or None for cached-only mode.
        use_cached:   If True, skip Trino and load from existing parquet.

    Returns:
        DataFrame of registered-school records (one row per school) with funnel
        status, measurement counts, ISP/server nested dicts, and admin metadata.
    """
    path = Path(path)

    if use_cached:
        if not path.exists():
            raise FileNotFoundError(
                f"Registration data not available and USE_CACHED_DATA=True. "
                f"Provide {path} or set USE_CACHED_DATA=False with a Trino connection."
            )
        r = pd.read_parquet(path)
        print(f"✓ Registration data loaded from cache: {r.shape[0]:,} rows  ({path.name})")
        return r

    if cur is None:
        raise FileNotFoundError(
            f"USE_CACHED_DATA=False but no Trino connection. "
            f"Call get_trino_cursor() first, or set USE_CACHED_DATA=True if {path.name} exists."
        )

    query = f"""
        SELECT *
        FROM default.all_gigameter_registered_schools
        WHERE iso3_code = '{country_iso3.upper()}'
    """

    cur.execute(query)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    r = pd.DataFrame(rows, columns=cols)
    print(f"  {len(r):,} registration rows fetched")

    path.parent.mkdir(parents=True, exist_ok=True)
    r.to_parquet(path, index=False)
    print(f"✓ Registration data loaded and cached: {r.shape[0]:,} rows  ({path.name})")
    return r


def _load_country_reference(ref_path: Path | None = None) -> dict:
    if ref_path is None:
        # Walk up from this file's location looking for data/country_reference.json
        candidates = [
            Path(__file__).parent / "country_reference.json",
            Path.home() / "Documents/Giga/Delivery/Ad-Hoc/IQB-Edu/2026-04-iqb-edu/data/country_reference.json",
        ]
        for p in candidates:
            if p.exists():
                return json.loads(p.read_text())
        raise FileNotFoundError(
            "country_reference.json not found. Pass ref_path explicitly."
        )
    return json.loads(Path(ref_path).read_text())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Refresh country measurement parquets from Trino")
    parser.add_argument("countries", nargs="*", help="ISO3 codes to refresh, e.g. MWI LKA")
    parser.add_argument("--all", action="store_true", help="Refresh all countries in country_reference.json")
    parser.add_argument("--ref", default=None, help="Path to country_reference.json")
    parser.add_argument("--base", default=None, help="Base directory for parquet files")
    args = parser.parse_args()

    ref = _load_country_reference(args.ref)

    if args.all:
        targets = list(ref.keys())
    elif args.countries:
        targets = args.countries
    else:
        parser.print_help()
        sys.exit(0)

    base = Path(args.base) if args.base else Path.home() / "Documents/Giga/Delivery"
    cur = get_trino_cursor()
    if cur is None:
        sys.exit(1)

    for iso3 in targets:
        if iso3 not in ref:
            print(f"{iso3}: not in country_reference.json, skipped")
            continue
        country_name = ref[iso3]["name"]
        parquet_path = base / f"Countries/{country_name}/{country_name.lower().replace(' ', '')}_measurements.parquet"
        print(f"\n── {iso3} ({country_name}) ──")
        refresh_country(iso3, parquet_path, cur, country_name)

    print("\nDone.")
