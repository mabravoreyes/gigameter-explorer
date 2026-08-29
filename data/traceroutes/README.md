# Traceroute datasets

M-Lab publishes a traceroute study per country at
<https://giga-traceroutes.measurementlab.net>, backed by one parquet per
country-month in the public bucket `gs://giga_traceroutes/parquet/`.
28 countries are available, six months each (Fiji and Malawi have seven),
latest July 2026.

## Layout

* `<ISO2>/` — committed exports for a country, plus a `manifest.json`
  (source object, rows, sha256) and a country `README.md`. Albania and Belize
  are committed; everything else is a fetch away.
* `country_profiles.csv` — one row per country summarising all 28, written by
  `helpers/traceroute_profiles.py`.

## Fetching

```bash
python helpers/fetch_traceroutes.py --list                 # inventory
python helpers/fetch_traceroutes.py KE                     # commit-tracked
python helpers/fetch_traceroutes.py --all --dest cache/traceroutes --max-mb 70
```

`--dest` keeps a bulk pull out of git. Uzbekistan is the reason for `--max-mb`:
its monthly exports run 168-286 MB, 1,008 MB against 217 MB for the other 27
countries combined.

## Reading `country_profiles.csv`

Use `traceroute_profiles.read_profiles()`, not a bare `pd.read_csv`. Namibia's
ISO-2 code is `NA`, which pandas reads as a missing value by default and would
drop the country from any grouping.

Two columns need care before anything is compared across countries:

* **`months`** — how many months were on disk when the profile ran, not what
  the site publishes. Uzbekistan shows 2 because the bulk pull skipped its
  large months; its figures describe June-July 2026 only.
* **`median_path_km` / `median_rtt_ms`** — each country is measured against
  whichever M-Lab servers serve it. Kenya's 13 km and Mongolia's 11 km mean the
  server is domestic; Kazakhstan's 11,640 km means it is not. These are **not**
  a ranking of connectivity quality, and comparing them across countries
  compares server placement. The concentration measures (`access_hhi`,
  `transit_hhi`, `single_homed_pct`) are comparable; the distances are not.

Countries with very few traces cannot support a claim: Saint Kitts has 4 traces
in one month, Congo 105 with no completed paths, Grenada 136.
