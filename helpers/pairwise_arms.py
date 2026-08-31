"""
School-attributed against unattributed traces, within network-server pairs.

The published exports are every NDT client in a country, and `join_schools`
splits them by whether the test's UUID is known to the Giga Meter backend. This
module compares the two arms *inside* a network-server cell, so a difference
cannot be the access ISP and cannot be the M-Lab server: both are held fixed.

Usage - from a notebook:
    import sys; sys.path.insert(0, 'helpers')
    from pairwise_arms import arm_frame, stratum_table, pooled_delta, run

    f = arm_frame('AL')                       # traces + arm + local clock
    stratum_table(f)                          # one row per network x server x time cell
    pooled_delta(f, 'ndt_rtt')                # crude vs stratified, with a CI
    run(['AL', 'LK'])                         # one row per country x metric

Usage - from the command line:
    python helpers/pairwise_arms.py                     # every country on disk
    python helpers/pairwise_arms.py AL LK --min-n 50
    python helpers/pairwise_arms.py --root ../gigameter-traceroute-data/traceroutes

WHAT THE TWO ARMS ARE, AND ARE NOT
The `school` arm is a trace whose NDT UUID joins to a Giga-registered school.
The other arm is `unattributed`: the backend has no record of that test. It is
NOT verified non-school traffic. It certainly holds household and business
clients on the same networks, but it also holds school tests the backend never
recorded, so the contrast is attribution, not premises. Every figure here
should be read and reported that way.

WHY THE STRATIFICATION IS NOT OPTIONAL
The arms are sampled from different clocks. In Albania 22% of school traces
land in the 08:00 hour against 4% of unattributed ones, which sit in the
residential evening peak; school traces are 92% weekday against 75%. Comparing
the arms without holding the hour fixed measures time of day. `pooled_delta`
therefore reports the crude and the stratified estimate side by side, computed
over the same rows, so the size of that confound is visible rather than
assumed.

METRICS, AND ONE TO DISTRUST
`ndt_rtt` is reported as a median difference in ms, `ndt_throughput` as a
log-ratio (school / unattributed), `is_reaching_dst_asn` in percentage points.
`ndt_loss_rate` is available but is a retransmission rate, and retransmission
rises with throughput - an arm that transfers faster will show more of it. It
is excluded from `METRICS` for that reason; pass it explicitly if wanted, and
do not read it as a school-side loss problem.

Direction of measurement is M-Lab's: every path runs from the server towards
the client, so `src_*` is the client in-country and `dst_site` the server.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from join_schools import attach_schools, school_index
from load_traceroutes import load_traceroutes

_ROOT = Path(__file__).resolve().parent.parent
_REFERENCE = json.loads((Path(__file__).resolve().parent / "country_reference.json").read_text())

# Most cached school indexes cover this window; a country whose cache differs
# (Grenada stops at June) is read from its own cache instead - see
# `cached_window`. Traces outside the index window would be unattributable by
# construction and would inflate the unattributed arm.
INDEX_START, INDEX_END = "2026-02-01", "2026-07-31"

# Held fixed in every comparison: the access network and the M-Lab server.
PAIR = ["src_asn", "dst_site"]
# Added on top for the stratified estimate: the clock the two arms differ on.
CLOCK = ["daypart", "weekend"]

# (column, kind) - 'diff' reports school minus unattributed in the column's own
# units, 'logratio' reports school / unattributed, 'pp' reports a rate in points.
METRICS = {
    "ndt_rtt": "diff",
    "ndt_throughput": "logratio",
    "is_reaching_dst_asn": "pp",
}

_COLUMNS = ["id", "partition_date", "window_start", "src_asn", "src_asn_name",
            "dst_site", "dst_asn", "ndt_rtt", "ndt_throughput", "ndt_loss_rate",
            "is_reaching_dst_asn", "forward_distance"]


def iso3_of(iso2: str) -> str:
    """ISO-3 for a traceroute directory name, e.g. 'AL' -> 'ALB'."""
    for code, meta in _REFERENCE.items():
        if meta["iso2"] == iso2.upper():
            return code
    raise KeyError(f"No ISO-3 for {iso2!r} in country_reference.json")


def cached_window(iso3: str) -> tuple[str, str]:
    """
    The widest school-index window already cached for `iso3`.

    Keeps the sweep offline and correct at once: every country is compared over
    the window its own index actually covers, rather than a shared window that
    would silently query Trino for the countries that do not match it.
    """
    cached = sorted((_ROOT / "cache" / iso3).glob("school_index_*.parquet"))
    if not cached:
        raise FileNotFoundError(f"No cached school index for {iso3}")
    windows = [path.stem.replace("school_index_", "").split("_") for path in cached]
    return max(windows, key=lambda w: (pd.Timestamp(w[1]) - pd.Timestamp(w[0])).days)


def _local_clock(frame: pd.DataFrame, iso3: str) -> pd.DataFrame:
    """
    Attach the client's local hour, weekday and 3-hour daypart.

    Uses the country's tz from country_reference rather than a longitude
    estimate: the daypart buckets are only three hours wide, so an hour of
    error would move traces between them.
    """
    tz = _REFERENCE[iso3]["timezone"]
    local = pd.to_datetime(frame["window_start"], utc=True).dt.tz_convert(tz)
    frame = frame.copy()
    frame["hour"] = local.dt.hour
    frame["weekend"] = local.dt.dayofweek >= 5
    frame["daypart"] = (frame["hour"] // 3) * 3
    return frame


def arm_frame(country: str = "AL", iso3: str | None = None,
              data_root: Path | str | None = None,
              start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """
    Traces for `country` labelled `school` or `unattributed`, on the local clock.

    Restricted to the school index's own window: a month the index does not
    cover would read as wholly unattributed and is not evidence of anything.
    Join coverage is left on `frame.attrs['attribution']`.
    """
    iso3 = iso3 or iso3_of(country)
    if start is None or end is None:
        start, end = cached_window(iso3)
    tr = load_traceroutes(country, columns=_COLUMNS, data_root=data_root)
    tr = tr[tr["partition_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    if tr.empty:
        raise ValueError(f"{country}: no traces inside {start}..{end}")

    index = school_index(iso3, start, end)
    frame = attach_schools(tr, index[["measurement_uuid", "school_id_giga"]], how="left")
    frame["arm"] = np.where(frame["school_id_giga"].notna(), "school", "unattributed")
    frame = _local_clock(frame, iso3)
    frame.attrs["attribution"] = {
        "country": country,
        "traces": len(frame),
        "school": int((frame["arm"] == "school").sum()),
        "school_pct": round(100 * (frame["arm"] == "school").mean(), 1),
        "schools": int(frame["school_id_giga"].nunique()),
        "window": f"{start}..{end}",
    }
    return frame


def _summarise(group: pd.DataFrame, metrics: dict) -> pd.Series:
    """
    A cell's centre per metric. Rates take a mean, everything else a median:
    `is_reaching_dst_asn` is a 0/1 flag whose median is 0 or 1 and never a rate.
    """
    out = {"n": len(group)}
    for column, kind in metrics.items():
        series = group[column].dropna()
        if not len(series):
            out[column] = np.nan
        else:
            out[column] = series.mean() if kind == "pp" else series.median()
    return pd.Series(out)


def stratum_table(frame: pd.DataFrame, metrics: dict | None = None,
                  min_n: int = 30, keys: list[str] | None = None) -> pd.DataFrame:
    """
    One row per cell, with each arm's medians side by side.

    `keys` defaults to the network-server pair plus the clock. Cells are kept
    only where BOTH arms carry at least `min_n` traces - a cell the school arm
    alone occupies says nothing about a difference.
    """
    metrics = metrics or METRICS
    keys = keys or PAIR + CLOCK
    wide = (frame.groupby(keys + ["arm"], observed=True)
                 .apply(_summarise, metrics=metrics, include_groups=False)
                 .unstack("arm"))
    counts = wide["n"].reindex(columns=["school", "unattributed"]).fillna(0)
    wide = wide[(counts["school"] >= min_n) & (counts["unattributed"] >= min_n)]
    return wide


def _effect(school: float, other: float, kind: str) -> float:
    if not np.isfinite(school) or not np.isfinite(other):
        return np.nan
    if kind == "logratio":
        return np.log(school / other) if school > 0 and other > 0 else np.nan
    if kind == "pp":
        return 100 * (school - other)
    return school - other


def _weights(counts: pd.DataFrame) -> pd.Series:
    """Effective sample size of a cell - a cell is only as strong as its thinner arm."""
    return 1.0 / (1.0 / counts["school"] + 1.0 / counts["unattributed"])


def pooled_delta(frame: pd.DataFrame, metric: str = "ndt_rtt",
                 kind: str | None = None, min_n: int = 30,
                 n_boot: int = 1000, seed: int = 0) -> dict:
    """
    The crude and the stratified school-minus-unattributed effect, on one row set.

    Both estimates are computed over the traces that survive the stratified
    cell filter, so they differ only by whether the clock is held fixed. The
    crude figure is the pooled median difference across those rows; the
    stratified figure is the weighted mean of the within-cell differences,
    weighted by effective sample size.

    The CI is a bootstrap over cells, not over traces: cells are the unit that
    varies, and resampling traces would treat a country's cell structure as
    certain when it is exactly what a second month could change.
    """
    kind = kind or METRICS.get(metric, "diff")
    keys = PAIR + CLOCK
    cells = stratum_table(frame, {metric: kind}, min_n=min_n, keys=keys)
    if cells.empty:
        return {"metric": metric, "cells": 0, "traces": 0, "crude": np.nan,
                "stratified": np.nan, "lo": np.nan, "hi": np.nan}

    kept = frame.set_index(keys).index.isin(cells.index)
    rows = frame[kept]
    centre = (lambda s: s.mean()) if kind == "pp" else (lambda s: s.median())
    crude_school = centre(rows.loc[rows["arm"] == "school", metric].dropna())
    crude_other = centre(rows.loc[rows["arm"] == "unattributed", metric].dropna())

    effects = cells[metric].apply(
        lambda row: _effect(row["school"], row["unattributed"], kind), axis=1)
    weights = _weights(cells["n"])
    keep = effects.notna()
    effects, weights = effects[keep], weights[keep]

    stratified = float(np.average(effects, weights=weights)) if len(effects) else np.nan

    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(effects), len(effects))
        draws.append(np.average(effects.to_numpy()[pick], weights=weights.to_numpy()[pick]))
    lo, hi = (np.percentile(draws, [2.5, 97.5]) if len(effects) > 1 else (np.nan, np.nan))

    return {
        "metric": metric,
        "kind": kind,
        "cells": int(len(effects)),
        "networks": int(cells.index.get_level_values("src_asn").nunique()),
        "servers": int(cells.index.get_level_values("dst_site").nunique()),
        "traces": int(len(rows)),
        "n_school": int((rows["arm"] == "school").sum()),
        "n_other": int((rows["arm"] == "unattributed").sum()),
        "crude": _effect(crude_school, crude_other, kind),
        "stratified": stratified,
        "lo": float(lo),
        "hi": float(hi),
    }


def clock_gap(frame: pd.DataFrame) -> dict:
    """
    How differently the two arms are sampled in time - the confound, quantified.

    `tvd` is the total variation distance between the arms' hour-of-day
    distributions: 0 means identically sampled, 1 means no overlap at all.
    """
    hours = (frame.groupby(["arm", "hour"]).size().unstack("arm", fill_value=0))
    shares = hours / hours.sum()
    if "school" not in shares or "unattributed" not in shares:
        return {"tvd": np.nan, "school_weekday_pct": np.nan, "other_weekday_pct": np.nan}
    weekday = 100 * (~frame["weekend"]).groupby(frame["arm"]).mean()
    return {
        "tvd": round(float(0.5 * (shares["school"] - shares["unattributed"]).abs().sum()), 3),
        "school_weekday_pct": round(float(weekday.get("school", np.nan)), 1),
        "other_weekday_pct": round(float(weekday.get("unattributed", np.nan)), 1),
    }


def country_rows(country: str, data_root: Path | str | None = None,
                 metrics: dict | None = None, min_n: int = 30) -> list[dict]:
    """One row per metric for `country`, or [] if nothing is comparable."""
    metrics = metrics or METRICS
    frame = arm_frame(country, data_root=data_root)
    attribution, clock = frame.attrs["attribution"], clock_gap(frame)
    rows = []
    for metric, kind in metrics.items():
        result = pooled_delta(frame, metric, kind, min_n=min_n)
        if not result["cells"]:
            continue
        rows.append({**{"country": country}, **attribution, **clock, **result})
    return rows


def run(countries: list[str] | None = None, data_root: Path | str | None = None,
        min_n: int = 30, metrics: dict | None = None, verbose: bool = False) -> pd.DataFrame:
    """The cross-country table: every country with a comparable cell, one row per metric."""
    root = Path(data_root or _ROOT / "data" / "traceroutes")
    countries = countries or sorted(
        d.name for d in root.iterdir() if d.is_dir() and len(d.name) == 2)
    rows, skipped = [], []
    for country in countries:
        if verbose:
            print(f"  {country} ...", flush=True)
        try:
            found = country_rows(country, data_root=root, metrics=metrics, min_n=min_n)
        except (FileNotFoundError, ValueError, KeyError) as error:  # no data, no index, no window
            skipped.append((country, str(error)[:60]))
            continue
        if found:
            rows.extend(found)
        else:
            skipped.append((country, f"no cell with {min_n}+ in both arms"))
    table = pd.DataFrame(rows)
    table.attrs["skipped"] = skipped
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("countries", nargs="*", help="ISO-2 codes; default every country on disk")
    parser.add_argument("--root", default=None, help="traceroute tree to read")
    parser.add_argument("--min-n", type=int, default=30, help="minimum traces per arm per cell")
    parser.add_argument("--out", default="data/traceroutes/pairwise_arms.csv")
    args = parser.parse_args()

    table = run(args.countries or None, data_root=args.root, min_n=args.min_n, verbose=True)
    if table.empty:
        print("No country had a comparable cell.")
    else:
        pd.set_option("display.width", 200)
        print(table.to_string(index=False))
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.out, index=False)
        print(f"\nWrote {args.out}")
    for country, reason in table.attrs["skipped"]:
        print(f"  skipped {country}: {reason}")


if __name__ == "__main__":
    main()
