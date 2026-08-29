"""
Fetch M-Lab traceroute exports from the Giga public bucket.

The site at giga-traceroutes.measurementlab.net publishes one parquet per
country-month to a public Google Cloud Storage bucket. This module lists what
is available and downloads it into `data/traceroutes/<ISO2>/`, using the same
`giga_<ISO2>_<YYYY>-<MM>.parquet` naming and manifest that the committed
Albania files already follow, so `load_traceroutes()` picks them up unchanged.

Usage — from the command line:
    python helpers/fetch_traceroutes.py --list            # inventory, by country
    python helpers/fetch_traceroutes.py BZ                # every month for Belize
    python helpers/fetch_traceroutes.py AL --months 2026-04
    python helpers/fetch_traceroutes.py --all --max-mb 50 # every country, skipping big ones

Usage — from a notebook:
    import sys; sys.path.insert(0, 'helpers')
    from fetch_traceroutes import inventory, fetch_country
    inv = inventory()
    fetch_country('BZ')

Only the parquet is downloaded; nothing is committed. A country pulled here is
tracked by git only if you `git add` it — check the size first, some countries
run to hundreds of megabytes per month.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

BUCKET = "giga_traceroutes"
PREFIX = "parquet/"
_LIST_URL = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
_OBJECT_URL = f"https://storage.googleapis.com/{BUCKET}/{PREFIX}"

_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "traceroutes"

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
           "december": 12}

# Most objects are named giga_<CC>_<monthname><year>; a couple of early ones
# already carry an ISO month, so both spellings are accepted.
_NAMED = re.compile(rf"^{PREFIX}giga_([A-Z]{{2}})_([a-z]+)(\d{{4}})\.parquet$")
_ISO = re.compile(rf"^{PREFIX}giga_([A-Z]{{2}})_(\d{{4}})-(\d{{2}})\.parquet$")


def _parse(name: str) -> tuple[str, str] | None:
    """Object name -> (ISO2, 'YYYY-MM'), or None if it is not a country export."""
    m = _NAMED.match(name)
    if m:
        country, month, year = m.groups()
        if month in _MONTHS:
            return country, f"{year}-{_MONTHS[month]:02d}"
        return None
    m = _ISO.match(name)
    if m:
        country, year, month = m.groups()
        return country, f"{year}-{month}"
    return None


def inventory() -> dict[str, dict[str, dict]]:
    """
    List every published export as {ISO2: {'YYYY-MM': {...}}}.

    Each entry carries the object name, byte size and the bucket's md5/crc32c,
    so a later fetch can be checked without re-reading the file.
    """
    out: dict[str, dict[str, dict]] = {}
    token = None
    while True:
        url = f"{_LIST_URL}?prefix={PREFIX}&maxResults=1000"
        if token:
            url += f"&pageToken={token}"
        with urllib.request.urlopen(url, timeout=120) as response:
            page = json.load(response)
        for item in page.get("items", []):
            parsed = _parse(item["name"])
            if parsed is None:
                continue
            country, month = parsed
            out.setdefault(country, {})[month] = {
                "object": item["name"],
                "bytes": int(item["size"]),
                "md5": item.get("md5Hash"),
                "updated": item.get("updated"),
            }
        token = page.get("nextPageToken")
        if not token:
            return out


def fetch_country(
    country: str,
    months: list[str] | None = None,
    inv: dict | None = None,
    max_mb: float | None = None,
    overwrite: bool = False,
    dest_root: Path | str | None = None,
) -> list[Path]:
    """
    Download a country's exports into `<dest_root>/<ISO2>/`.

    months    — e.g. ['2026-04']; None fetches every published month.
    max_mb    — skip any single file larger than this, for the countries whose
                monthly export runs to hundreds of megabytes.
    overwrite — re-download files already on disk.
    dest_root — where to write; defaults to `data/traceroutes/`, which is
                tracked. Point it at `cache/` for a bulk pull you do not intend
                to commit.

    Writes a manifest alongside the parquet, matching the committed Albania one.
    """
    country = country.upper()
    inv = inv if inv is not None else inventory()
    if country not in inv:
        raise KeyError(f"{country!r} is not in the bucket; try inventory().keys()")

    target = Path(dest_root or _DATA_ROOT) / country
    target.mkdir(parents=True, exist_ok=True)
    wanted = sorted(months or inv[country])

    written = []
    for month in wanted:
        entry = inv[country].get(month)
        if entry is None:
            print(f"  {country} {month}: not published, skipping")
            continue
        size_mb = entry["bytes"] / 1e6
        if max_mb is not None and size_mb > max_mb:
            print(f"  {country} {month}: {size_mb:,.1f} MB exceeds --max-mb, skipping")
            continue

        destination = target / f"giga_{country}_{month}.parquet"
        if destination.exists() and not overwrite:
            print(f"  {country} {month}: already on disk, skipping")
            written.append(destination)
            continue

        url = _OBJECT_URL + entry["object"].removeprefix(PREFIX)
        print(f"  {country} {month}: fetching {size_mb:,.1f} MB", flush=True)
        urllib.request.urlretrieve(url, destination)
        written.append(destination)

    _write_manifest(country, target, inv)
    return written


def _write_manifest(country: str, target: Path, inv: dict) -> None:
    """Record provenance for whatever is currently on disk for this country."""
    import pyarrow.parquet as pq

    files = []
    for path in sorted(target.glob(f"giga_{country}_*.parquet")):
        month = path.stem.rsplit("_", 1)[-1]
        metadata = pq.read_metadata(path)
        table = pq.read_table(path, columns=["partition_date"]) if metadata.num_rows else None
        dates = table.to_pydict()["partition_date"] if table is not None else []
        files.append({
            "file": path.name,
            "month": month,
            "rows": metadata.num_rows,
            "columns": metadata.num_columns,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "date_min": str(min(dates)) if dates else None,
            "date_max": str(max(dates)) if dates else None,
            "distinct_days": len(set(dates)),
            "bucket_object": inv.get(country, {}).get(month, {}).get("object"),
        })

    (target / "manifest.json").write_text(json.dumps({
        "source_url": f"https://giga-traceroutes.measurementlab.net/country/{country.lower()}.html",
        "bucket": f"gs://{BUCKET}/{PREFIX}",
        "country_iso2": country,
        "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "files": files,
    }, indent=2) + "\n")


def _print_inventory(inv: dict) -> None:
    months = sorted({m for country in inv.values() for m in country})
    print(f"{'cc':4s}" + "".join(f"{m:>10s}" for m in months) + f"{'total':>11s}")
    grand = 0
    for country in sorted(inv):
        line = f"{country:4s}"
        for month in months:
            entry = inv[country].get(month)
            line += f"{entry['bytes'] / 1e6:>9.1f} " if entry else f"{'-':>9s} "
        total = sum(e["bytes"] for e in inv[country].values())
        grand += total
        print(line + f"{total / 1e6:>9.1f}MB")
    print(f"\n{len(inv)} countries, "
          f"{sum(len(c) for c in inv.values())} files, {grand / 1e6:,.0f} MB total")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("countries", nargs="*", help="ISO2 codes, e.g. AL BZ")
    parser.add_argument("--list", action="store_true", help="show the inventory and exit")
    parser.add_argument("--all", action="store_true", help="fetch every country")
    parser.add_argument("--months", nargs="+", help="limit to these months, e.g. 2026-04")
    parser.add_argument("--max-mb", type=float, help="skip files larger than this")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dest", help="write here instead of data/traceroutes/ "
                                       "(e.g. cache/traceroutes for a bulk pull)")
    args = parser.parse_args(argv)

    inv = inventory()
    if args.list or (not args.countries and not args.all):
        _print_inventory(inv)
        return 0

    for country in (sorted(inv) if args.all else args.countries):
        print(f"{country}:")
        fetch_country(country, months=args.months, inv=inv, max_mb=args.max_mb,
                      overwrite=args.overwrite, dest_root=args.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
