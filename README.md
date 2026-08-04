# Giga Meter EDA Explorer

[Giga Meter](https://giga.global/) is the school-side measurement application of Giga, the UNICEF–ITU initiative to connect every school to the internet. It runs speed tests and connectivity checks from a device inside the school and reports the results centrally. 

This repository contains a single country-parameterized notebook, `gigameter_eda_explorer.ipynb`, which templatizes EDA for Giga Meter data. It covers the following main areas:
* deployment funnel and installation growth
* adoption and retention
* connectivity performance distributions & IQB-Edu distributions
* ISP comparisons

The Appendix contains various deep dives covering drop-off, speed consistency, throttling and hard-cap detection, hourly congestion profiles, WiFi versus Ethernet, and per-school anomaly flags.

The same notebook serves deployments of very different sizes. Data pulls stream to parquet in batches once a country exceeds one million rows, and two read-time knobs (`ROWLEVEL_WINDOW_DAYS`, `LOAD_COLUMNS`) bound what is loaded into memory — a few hundred schools load in full, while a multi-million-row deployment can be scoped to a trailing window without changing any analysis code. Configuration is a single cell; the analysis is the same for every country.

A scope note on the data. Measurements come from the consolidated table `all_gigameter_measurement_data`, which lags roughly one day — the freshest observable activity is "yesterday", not "today". The `pass_fail_overall` field is a measurement-validity flag, not a quality verdict; the notebook uses it to exclude unreliable tests. Measured speeds reflect conditions at a device on the school network, and are bounded by — not equal to — contracted capacity.

## Data access

Running the notebook requires Trino access to the Giga data platform, granted by the Giga DevOps team. 
School master data (education levels, admin regions) additionally requires a Delta Sharing profile — place your `prd_profile.share` in `helpers/`, or skip the master cell and work from measurements alone.

## Connecting to Trino

The helpers expect Trino on `localhost:8080` (`_TRINO_PRD` in `helpers/load_measurements.py`).

1. **Giga cluster port-forward** (default) — with `az`, `kubectl`, and `kubelogin` configured for the cluster:
   ```bash
   kubectl port-forward svc/trino 8080:8080 -n ictd-ooi-trino-prd
   ```
   The helpers auto-start this if the port is closed.
2. **Your own endpoint** — edit `_TRINO_PRD` (host, port, user, catalog) in `helpers/load_measurements.py`.

New to the platform? `trino_starter.ipynb` walks through the one-time setup (`az` / `kubectl` / `kubelogin`), verifies the connection, and shows how to discover catalogs and run ad-hoc queries before diving into the full explorer.

## Running

1. `pip install -r requirements.txt` (Python 3.11+)
2. Open `gigameter_eda_explorer.ipynb` and set the **CONFIG cell**:
   - `COUNTRY_ISO3`, `COUNTRY_ISO2`, `COUNTRY_NAME`, `TIMEZONE`
   - `USE_CACHED_DATA = False` on first run — pulls from Trino and caches to `./cache/<Country>/`; `True` afterwards for offline work
   - `ROWLEVEL_WINDOW_DAYS` / `LOAD_COLUMNS` — leave `None` for small countries; set (e.g. `365`) for very large ones
3. Run top to bottom: Part A is the close-out narrative, Part B the appendix deep dives, Part C the exports.

## ISP canonicalisation

Raw ISP names split one provider across near-duplicate strings — quotes, legal suffixes, spacing, and occasionally distinct registered names for one operator. The ISP normalisation cell collapses these automatically and applies per-country overrides from `isp_mappings.json`, keyed by ISO3:

```json
{"FJI": {"Starlink": ["as14593", "space exploration technologies", "spacex", "starlink"]}}
```

Extend the file with a block for your country; patterns are lowercased substrings matched after cleaning.

## Known limits
* Traceroute section to be developed
* Ping data in process of being added
