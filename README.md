# Giga Meter Explorer

[Giga Meter](https://giga.global/) is the school-side measurement application of Giga, the UNICEF–ITU initiative to connect every school to the internet. It runs speed tests and connectivity checks from a device inside the school and reports the results centrally. 

This repository contains a numbered set of country-parameterized notebooks that templatize the work on Giga Meter data:

| Notebook | Role |
|---|---|
| `trino_starter_00.ipynb` | one-time Trino setup and connection check |
| `download_data_01.ipynb` | pulls and cleans the data, writes the analysis-ready dataset |
| `meter_explorer_02.ipynb` | exploratory analysis |
| `meter_baseline_03.ipynb` | connectivity baseline and ISP performance review |
| `meter_fleetprofile_04.ipynb` | fleet-wide profile: rhythm, seasonality, silence, churn, survivorship (server-side SQL) |
| `meter_dropoff_05.ipynb` | per-country drop-off: who stopped, when, and what predicts it |

Run the download/clean notebook first. It writes `<slug>_clean.parquet`, `<slug>_clean_unfiltered.parquet` and `<slug>_clean_params.json` to the country cache; both other notebooks open with a loader cell that reads those, so the cleaning decisions — servers kept, latency cutoff, school-hours window — are inherited rather than repeated, and every result traces back to the parameters that produced it.

**The EDA explorer** covers:
* deployment funnel and installation growth
* adoption and retention
* connectivity performance distributions & IQB-Edu distributions
* ISP comparisons

The Appendix contains various deep dives covering drop-off, speed consistency, throttling and hard-cap detection, hourly congestion profiles, WiFi versus Ethernet, and per-school anomaly flags.

**The baseline notebook** answers the questions a ministry asks when reviewing ISP contracts: when were the most schools actively reporting, what is the connectivity baseline per school, how do providers compare against an agreed threshold, and whether year-over-year changes are statistically significant. It is parameterized by education level and year, and includes an H3 hex-tile map of median bandwidth by area, a measurement-validity annex, and Superset-ready exports.

The same notebooks serve deployments of very different sizes. Data pulls stream to parquet in batches once a country exceeds one million rows, and two read-time knobs (`ROWLEVEL_WINDOW_DAYS`, `LOAD_COLUMNS`) bound what is loaded into memory — a few hundred schools load in full, while a multi-million-row deployment can be scoped to a trailing window without changing any analysis code. Configuration is a single cell; the analysis is the same for every country.

A scope note on the data. Measurements come from the consolidated table `all_gigameter_measurement_data`, which lags roughly one day — the freshest observable activity is "yesterday", not "today". The `pass_fail_overall` field is a measurement-validity flag, not a quality verdict; the notebooks use it to exclude unreliable tests. Measured speeds reflect conditions at a device on the school network, and are bounded by — not equal to — contracted capacity.

## Data access

Running the notebooks requires Trino access to the Giga data platform, granted by the Giga DevOps team. 
School master data (education levels, admin regions) additionally requires a Delta Sharing profile — place your `prd_profile.share` in `helpers/`, or skip the master cell and work from measurements alone.

## Connecting to Trino

The helpers expect Trino on `localhost:8080` (`_TRINO_PRD` in `helpers/load_measurements.py`).

1. **Giga cluster port-forward** (default) — with `az`, `kubectl`, and `kubelogin` configured for the cluster:
   ```bash
   kubectl port-forward svc/trino 8080:8080 -n ictd-ooi-trino-prd
   ```
   The helpers auto-start this if the port is closed.
2. **Your own endpoint** — edit `_TRINO_PRD` (host, port, user, catalog) in `helpers/load_measurements.py`.

New to the platform? `trino_starter_00.ipynb` walks through the one-time setup (`az` / `kubectl` / `kubelogin`), verifies the connection, and shows how to discover catalogs and run ad-hoc queries before diving into the notebooks.

## Running

1. `pip install -r requirements.txt` (Python 3.11+)
2. Open `download_data_01.ipynb` and set the **Country cell** — one code, e.g. `COUNTRY = "FJI"` (ISO3 or country name; iso2/name/timezone resolve automatically via `helpers/country_reference.json` + pytz). Data-loading options live in the same cell; notebook-level filters (region, school hours, minimum-data rules) and the analysis scope (education level, years, thresholds) in the cells after:
   - `USE_CACHED_DATA = False` on first run — pulls from Trino and caches to `./cache/<Country>/`; `True` afterwards for offline work
   - `ROWLEVEL_WINDOW_DAYS` / `LOAD_COLUMNS` — leave `None` for small countries; set (e.g. `365`) for very large ones
3. Run it top to bottom. Two choices are made from the data rather than assumed: the latency outlier cutoff and the school-hours window each show a distribution first, then apply your pick.
4. Open `meter_explorer_02.ipynb` or `meter_baseline_03.ipynb`, set the country in the loader cell, and run.

## ISP canonicalisation

Raw ISP names split one provider across near-duplicate strings — quotes, legal suffixes, spacing, and occasionally distinct registered names for one operator. The ISP normalisation cell collapses these automatically and applies per-country overrides from `isp_mappings.json`, keyed by ISO3:

```json
{"FJI": {"Starlink": ["as14593", "space exploration technologies", "spacex", "starlink"]}}
```

Extend the file with a block for your country; patterns are lowercased substrings matched after cleaning.

## Traceroute data

Monthly M-Lab traceroute exports are committed under `data/traceroutes/<ISO2>/`
(Albania so far), with provenance in `manifest.json` and the schema, direction
of measurement and caveats in the country's `README.md`. Load them with
`helpers/load_traceroutes.py`, which also reshapes hops into tidy frames:

```python
import sys; sys.path.insert(0, 'helpers')
from load_traceroutes import load_traceroutes, hop_frame, upstream_adjacency
tr = load_traceroutes('AL')
```

Two points decide whether a reading of this data holds. The traceroute runs
*from the M-Lab server towards the client*, so `src_*` is the school-side
network and `dst_*` the server — and because every trace starts at the same
server, only the hops adjacent to the client identify an ISP's own upstream.
And the exports cover all NDT clients in the country, not only schools; join
`id` (the NDT UUID) to `uuid` in the Giga Meter measurements to isolate schools.

## Known limits
* Traceroute analysis is bootstrapped: data and loader are in, per-country
  notebooks are not written yet
* Ping data in process of being added
