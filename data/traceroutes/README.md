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
