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

## What the published reports do that these files do not

From the site's methodology note: *"Measurements come from M-Lab: NDT speed
tests run by real users on school networks, annotated with per-hop routing
detail. We filter each dataset to known school IP ranges, reconstruct the
forward path to domestic and international test servers, and summarize path
length, exchange-point crossings, transit-country dependency, latency
decomposition, loss, and performance over time."*

**That filter is applied downstream of these files, not to them.** The parquet
is the pipeline's input — the Belize country page labels it *"everything
fetched"* and reports the school-filtered subset separately. For Belize,
July 2026:

| | this parquet | the published report |
|---|---:|---:|
| rows | 1,316 | 889 school measurements |
| distinct client IPs | 204 | 28 school IPs |
| tests to `mex01` / `mex04` | 698 / 618 | 442 / 447 |
| AS10269 tests / IPs | 1,311 / 202 | 888 / 27 |
| reachability | 23.7% | 14.7% |

So the school-IP filter removes about a third of the rows and seven eighths of
the addresses. **Anything computed here describes NDT clients in the country,
not schools**, unless the filter is reproduced first — and it cannot be
reproduced from these files alone, because the school IP ranges are Giga's and
are not in the data.

The route to it is the `id` column. The published reports do exactly this in
their School-Level Study: they join the NDT UUID that both the traceroute
record and the Giga Meter API carry, attributing 873 of 889 Belize traceroutes
to 23 schools. That join also settles a question these files cannot: the report
finds 23 IPs carrying 23 schools and warns the 1.00x agreement is coincidence,
so **any per-school figure derived from counting client IPs is distorted**.

Timing still shows the population is school-*dominated* — 60% of Albanian
traces fall in the weekday 08:00-15:59 window against 24% under a uniform
clock — which is consistent with roughly two thirds of rows surviving the
filter. That is evidence about the mix, not a substitute for the filter.

## Direction of measurement

The site states it outright: *"Every path is a traceroute from an M-Lab server
towards the school. Routing is often asymmetric, so these findings need not
hold for traffic leaving the school."* This matches what Q0 of the notebook
verifies from the data — every path begins in `dst_asn`.

Two further definitions from the same note, worth carrying into any reading:
*"Loss is not reachability"* — loss is end-to-end from the NDT transfer, while
reachability is whether traceroute probes arrived, and a transfer can show zero
loss while its traceroute stops short. And *"thresholds are relative"* — the
published "underserved", "high" and "low" cuts come from each country's own
distribution and do not compare across countries.

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


## The Wi-Fi profile

`wifi_profiles.csv` answers the published reports' Wi-Fi section across every
country at once. Two columns carry the finding:

* **`capable_hw_pct`** — share of tests on hardware that can use 5 GHz
  (802.11ac or ax). 84% across all countries.
* **`capable_on_24ghz_pct`** — share of *that* hardware observed on 2.4 GHz
  anyway. 64% across all countries, and above 85% in Kazakhstan, Zambia,
  Malawi and Uzbekistan.

On capable hardware, 2.4 GHz negotiates a median 81 Mb/s and delivers 15.1;
5 GHz negotiates 433 and delivers 56.5. Of 3,508 schools with capable hardware
and at least five tests, 1,572 (44.8%) are never observed on 5 GHz at all.

One caveat governs how far that can be pushed. `wifi_model` names the
**client's** adapter, not the access point, so "capable hardware" means a
capable laptop. A school whose tests never reach 5 GHz may have an access point
that cannot offer it, in which case the fix is procurement rather than
configuration — but the measurement cannot tell those two apart, and neither
can this column.

The radio's negotiated rate correlates with throughput across schools in 12 of
21 countries with enough schools to test; signal strength does so in 3. What
varies with the result is the link the radio negotiated, not how well it is
receiving.
