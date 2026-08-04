"""
School master data loading — Delta Sharing (default) or Trino PRD.

Single source of truth for getting country master data into a CSV cache.
Notebooks should use load_master() rather than embedding the logic directly.

Usage — from a notebook:
    import sys
    sys.path.insert(0, str(Path.home() / 'Documents/Giga/Delivery/Ingestion/Set-Up'))
    from load_master import load_master, load_master_trino

    # Delta Sharing (no port-forward needed):
    master = load_master(COUNTRY_ISO3, master_cache, use_cached=USE_CACHED_DATA)

    # Trino PRD (requires kubectl port-forward svc/trino 8080:8080 -n ictd-ooi-trino-prd):
    master = load_master_trino(COUNTRY_ISO3, master_cache)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# PRD Trino — same params as trino_starter.ipynb
_TRINO_PRD = dict(
    host="localhost",
    port=8080,
    user="giga-trino",
    catalog="delta_lake",
    schema="default",
    http_scheme="http",
)


def _ensure_port_forward() -> bool:
    """Auto-start kubectl port-forward if port 8080 is not reachable."""
    import socket, subprocess, time
    def _open():
        try:
            with socket.create_connection(("localhost", 8080), timeout=1.5):
                return True
        except OSError:
            return False

    if _open():
        return True

    print("⏳ Starting kubectl port-forward for Trino PRD...")
    subprocess.Popen(
        ["kubectl", "port-forward", "svc/trino", "8080:8080", "-n", "ictd-ooi-trino-prd"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    if _open():
        print("✓ Port-forward running (localhost:8080)")
        return True
    print(
        "⚠️  Port-forward failed. Check az login / kubelogin, then retry or run:\n"
        "  kubectl port-forward svc/trino 8080:8080 -n ictd-ooi-trino-prd"
    )
    return False


def load_master(
    country_iso3: str,
    path: Path | str,
    use_cached: bool = True,
    credentials_dir: Path | None = None,
) -> pd.DataFrame:
    """
    Load school master data for a country, pulling from Delta Sharing if needed.

    Behaviour:
      - use_cached=True  + CSV exists  → load from disk, no network call.
      - use_cached=False               → pull from Delta Sharing, overwrite cache.
      - CSV missing regardless         → raises FileNotFoundError.

    Args:
        country_iso3:    ISO3 country code (e.g. 'LKA').
        path:            Path to the country master CSV cache.
        use_cached:      If True, skip Delta Sharing and load from existing CSV.
        credentials_dir: Directory containing prd_profile.share.
                         Defaults to ~/Documents/Giga/Delivery/Ingestion/Set-Up.

    Returns:
        DataFrame of school master records.
    """
    if credentials_dir is None:
        credentials_dir = Path(__file__).parent

    path = Path(path)

    if use_cached:
        if not path.exists():
            raise FileNotFoundError(
                f"Master data not available and USE_CACHED_DATA=True. "
                f"Provide {path} or set USE_CACHED_DATA=False to pull from Delta Sharing."
            )
        master = pd.read_csv(path)
        print(f"✓ Master data loaded from cache: {master.shape[0]:,} schools  ({path.name})")
        return master

    # use_cached=False — pull from Delta Sharing
    share_file = credentials_dir / "prd_profile.share"
    if not share_file.exists():
        raise FileNotFoundError(
            f"Delta Sharing credentials not found at {share_file}. "
            "Provide the file or set USE_CACHED_DATA=True if the CSV cache exists."
        )

    try:
        import delta_sharing
    except ImportError:
        raise ImportError(
            "delta_sharing is not installed — pip install delta-sharing. "
            f"Or set USE_CACHED_DATA=True if {path.name} already exists."
        )

    profile = str(share_file)
    table_url = profile + f"#gold.school-master.{country_iso3.lower()}"
    print(f"  Pulling master data from Delta Sharing for {country_iso3} (this may take a minute)...")

    master = delta_sharing.load_as_pandas(table_url)
    print(f"  {master.shape[0]:,} schools fetched")

    path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(path, index=False)

    print(f"✓ Master data loaded and cached: {master.shape[0]:,} schools  ({path.name})")
    return master


def load_master_trino(
    country_iso3: str,
    path: Path | str,
    engine=None,
) -> pd.DataFrame:
    """
    Pull school master from Trino PRD (delta_lake.school_master.<iso3>)
    and cache as CSV. Requires kubectl port-forward running.

    Args:
        country_iso3: ISO3 country code (e.g. 'LKA').
        path:         Path to save the CSV cache.
        engine:       Optional SQLAlchemy engine. If None, creates one using
                      the same params as trino_starter.ipynb.

    Returns:
        DataFrame of school master records.
    """
    path = Path(path)
    _ensure_port_forward()

    if engine is None:
        try:
            from sqlalchemy import create_engine
            engine = create_engine(
                f"trino://{_TRINO_PRD['user']}@{_TRINO_PRD['host']}:{_TRINO_PRD['port']}"
                f"/{_TRINO_PRD['catalog']}/{_TRINO_PRD['schema']}"
            )
        except Exception as e:
            raise RuntimeError(f"Could not create Trino engine: {e}")

    table = f"delta_lake.school_master.{country_iso3.lower()}"
    print(f"  Pulling master from Trino: {table} ...")

    master = pd.read_sql(f"SELECT * FROM {table}", engine)
    print(f"  {master.shape[0]:,} schools fetched")

    path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(path, index=False)

    print(f"✓ Master data loaded and cached: {master.shape[0]:,} schools  ({path.name})")
    return master
