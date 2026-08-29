# Traceroute datasets

M-Lab publishes a traceroute study per country at
<https://giga-traceroutes.measurementlab.net>, backed by one parquet per
country-month in the public bucket `gs://giga_traceroutes/parquet/`.
28 countries are available, six months each (Fiji and Malawi have seven),
latest July 2026.

## The parquet is not in this repository

This repository holds the analysis; the data lives in
**[gigameter-traceroute-data](https://github.com/mabravoreyes/gigameter-traceroute-data)**
(private). Keeping 244 MB of parquet out of the explorer is what makes it light
enough to clone and share — parquet is already compressed, so git cannot delta
it, and every committed copy costs its full size in history forever.

What stays here is the small, text-only part: this file, the per-country
`README.md` for the worked countries, each country's `manifest.json` (source
object, row counts, sha256 — so a run can be traced to exact files), and
`country_profiles.csv`, the 28-row cross-country summary.

## Getting the data

Either clone the data repository beside this one:

```bash
git clone https://github.com/mabravoreyes/gigameter-traceroute-data.git ../gigameter-traceroute-data
```

```python
tr = load_traceroutes('AL', data_root='../gigameter-traceroute-data/traceroutes')
```

Or re-fetch from the source bucket, which takes about a minute and produces
byte-identical files in `data/traceroutes/` where the notebook expects them:

```bash
python helpers/fetch_traceroutes.py --list                 # inventory
python helpers/fetch_traceroutes.py AL BZ                  # just what you need
python helpers/fetch_traceroutes.py --all --max-mb 100     # all 28 countries
python helpers/fetch_traceroutes.py UZ --dest cache/traceroutes   # UZ in full, ~1 GB
```

Fetched files are gitignored, so a pull never re-bloats this repository.

## Coverage gaps

**Uzbekistan is 2 of 6 months** in the data repository: its February-May 2026
exports are 271, 246, 286 and 168 MB and GitHub rejects any file over 100 MB.
`country_profiles.csv` records `months=2` for UZ. Use `--dest cache/traceroutes`
to fetch the full series outside git.

Every other country is complete. Where a country shows fewer than six months in
the profile, the site published an *empty* export for those months — Saint
Kitts has five empty of six — which is a property of the source, not a gap
here.

## What the publisher does upstream of these files

From the site's own methodology note: *"Measurements come from M-Lab: NDT speed
tests run by real users on school networks, annotated with per-hop routing
detail. We filter each dataset to known school IP ranges, reconstruct the
forward path to domestic and international test servers, and summarize path
length, exchange-point crossings, transit-country dependency, latency
decomposition, loss, and performance over time."*

Two consequences. The school filter is applied before publication, so these are
school measurements by construction rather than by inference. And the site's
own figures cover path length, IXP crossings, transit-country dependency,
latency decomposition, loss and change over time — `meter_traceroutes_07.ipynb`
covers the same ground in Q4-Q6, which is the closest this repo gets to
reproducing the published country pages.

Note that the array stored in `forward_updated_node_details` runs server to
client (verified in Q0: every path begins in `dst_asn`), the opposite of the
"forward path to test servers" reading its name suggests. The analysis takes
the hop adjacent to the client either way, so the direction changes the
interpretation, not the arithmetic.

## Reading `country_profiles.csv`

Use `traceroute_profiles.read_profiles()`, not a bare `pd.read_csv`. Namibia's
ISO-2 code is `NA`, which pandas reads as a missing value by default and would
drop the country from any grouping.

Three columns need care before anything is compared across countries:

* **`transit_readable`** — whether the transit columns can answer a question
  about market structure. Where the M-Lab server sits one hop from the client
  the AS path is just `[server, client]`, so the observed "upstream" is the
  network hosting the server. That adjacency is usually real — Kenyan schools
  genuinely do reach the server through KENET — but every path to that server
  must cross it, so a 92% top-upstream share is *forced by the measurement*
  rather than evidence of single-homing, and nothing here can show whether
  those ISPs hold other upstreams for other destinations. Kenya and South
  Africa read as 92% and 91% on exactly those paths, matching
  `upstream_is_server_pct` to the decimal. Seven countries are affected (BJ,
  KE, ZA, FJ, BW, MN, MW).

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
