# Belize traceroutes (M-Lab)

Monthly M-Lab traceroute exports for Belize, fetched from the Giga bucket with
`python helpers/fetch_traceroutes.py BZ`. `manifest.json` records the source
object, row counts and a sha256 per file.

| File | Rows |
|---|---:|
| `giga_BZ_2026-02.parquet` | 3,076 |
| `giga_BZ_2026-03.parquet` | 2,456 |
| `giga_BZ_2026-04.parquet` | 2,102 |
| `giga_BZ_2026-05.parquet` | 2,582 |
| `giga_BZ_2026-06.parquet` | 2,461 |
| `giga_BZ_2026-07.parquet` | 1,316 |

Schema, direction of measurement and the loader caveats are identical to
Albania's — see `../AL/README.md`. What differs is the market and the geography.

## Why this country is the contrast case to Albania

Albania's schools sit behind a fragmented access market (37-42 networks) whose
traffic converges on a handful of foreign transit providers. Belize is
concentrated at *both* layers:

* **Access.** Belize Telemedia Limited carries 92-99.7% of school traceroutes
  in every month observed — a single provider, not a market.
* **Transit.** Columbus Networks takes 89% of paths and Liberty Networks Mexico
  another 10%. Both are Liberty Latin America entities, so effectively one
  corporate group carries the country's school traffic. HHI 8,039.

The geography is more extreme than Albania's. Traces terminate at Mexico City
(`mex01`/`mex04`) and cross the US on 100% of paths, Mexico on 100% — and
**Chile on roughly a third**, a detour of thousands of kilometres to reach a
server two countries away. Median path length ranges 4,600-9,900 km against
Albania's 1,250 km, and median RTT sits at 72-82 ms.

`meter_traceroutes_07.ipynb` has a `COUNTRY_CONFIG` entry for `BZ`
(vantage points `mex01`/`mex04`, UTC-6, school year February-June); set
`COUNTRY_ISO2 = "BZ"` in the config cell and the notebook runs unchanged.

## Caveats specific to Belize

* Path completion is lower than Albania's: 38% of traces reach the client's
  ASN, so Q3-Q5 rest on a smaller base.
* Two vantage points carry comparable traffic (`mex04` 6,808 and `mex01`
  6,788 traces), so `PRIMARY_SITE` is a list here rather than a single site.
* With one access provider dominating, per-ISP comparison has nothing to
  compare. The within-ISP contrast still works: Belize Telemedia via Liberty
  Networks Mexico runs 4,516 km and 84 Mbps against 9,449 km and 40 Mbps via
  Columbus.
