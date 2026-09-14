#!/usr/bin/env python
"""Pull, clean and export one country's Giga Meter measurements — the scripted
form of download_data_01.ipynb, on the same shared pipeline (helpers/prepare.py).

    python scripts/download_data.py ZAF
    python scripts/download_data.py ZAF --admin1 "Eastern Cape" --latency-cutoff p99
    python scripts/download_data.py UZB --refresh --window-days 365

Writes {slug}_clean.parquet, {slug}_clean_unfiltered.parquet and
{slug}_clean_params.json (filters + full row-drop funnel) into cache/{Country}/.
The notebook remains the place to CHOOSE the latency cutoff interactively; the
script takes the choice as an argument and prints the candidates it did not take.
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "helpers"))

from prepare import (load_country, latency_cutoff_candidates,  # noqa: E402
                     prepare_country, export_clean)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("country", help="ISO3 code or country name")
    ap.add_argument("--admin1", default=None, help='scope to one region, e.g. "Eastern Cape"')
    ap.add_argument("--latency-cutoff", default="p99",
                    help="number (ms) or p95|p99|p99.5|iqr|modz (default p99)")
    ap.add_argument("--no-server-filter", action="store_true",
                    help="keep all measurement servers (default: dominant only)")
    ap.add_argument("--server-pct", type=float, default=0.30,
                    help="dominant-server share threshold (default 0.30)")
    ap.add_argument("--school-hours", default="7-16",
                    help="local school-hours window, inclusive (default 7-16)")
    ap.add_argument("--source", default=None, help="rt_source filter (default: all)")
    ap.add_argument("--refresh", action="store_true",
                    help="pull fresh from Trino instead of the parquet cache")
    ap.add_argument("--window-days", type=int, default=None,
                    help="only load the trailing N days (big countries)")
    ap.add_argument("--cache-root", default=str(REPO / "cache"))
    args = ap.parse_args()

    try:
        cutoff = float(args.latency_cutoff)
    except ValueError:
        cutoff = args.latency_cutoff
    start, end = (int(x) for x in args.school_hours.split("-"))

    L = load_country(args.country, use_cached=not args.refresh,
                     measurement_source=args.source,
                     rowlevel_window_days=args.window_days,
                     cache_root=args.cache_root)

    print("\nLatency-cutoff candidates (choice applied:", args.latency_cutoff, ")")
    print(latency_cutoff_candidates(L.m["latency"]).to_string(), "\n")

    P = prepare_country(L, latency_cutoff=cutoff,
                        server_filter=not args.no_server_filter,
                        server_pct=args.server_pct,
                        admin1=args.admin1, school_hours=(start, end))
    export_clean(P)


if __name__ == "__main__":
    main()
