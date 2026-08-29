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
country at once, from 455,970 Giga Meter measurements in 23 countries.

**5 GHz is better on average, but it is not deterministic and it is usually not
the constraint.** Three measurements say so.

*Within schools seen on both bands* — the only comparison that controls for the
connection behind the radio — 5 GHz is faster in 84.4% of 1,357 schools and
slower in 15.6% (Wilcoxon p ≈ 5e-166). Real, but not a rule: 5 GHz attenuates
faster and penetrates walls worse, so a school with distant or obstructed
access points can genuinely do better on 2.4 GHz.

*The gain barely converts.* Those same schools gain a median 361 Mb/s of
negotiated rate and 25.4 Mb/s of actual throughput — **7%**. The rest is
absorbed by whatever is upstream of the radio.

*And the radio is rarely what binds.* The median test uses 15% of its
negotiated rate, and only about 10% of tests reach half of it. For the other
90% the radio has five-fold headroom or more, so the band is not what is
holding those schools back.

### What moving a school to 5 GHz is actually worth

The question is not whether 5 GHz is better in principle but how much a school
gains, on how many schools the estimate rests, and against what it currently
gets. `wifi_profiles.csv` carries all three; ordered by gain against current
throughput, and keeping only countries whose estimate rests on 20 or more
schools seen on both bands:

| country | addressable schools | now | gain | vs now | evidence | faster on 5 GHz |
|---|---:|---:|---:|---:|---:|---:|
| Mongolia | 111 | 21.5 | +58.1 | +271% | 343 | 94.5% |
| Sri Lanka | 1,170 | 15.3 | +25.4 | +166% | 273 | 84.2% |
| Bosnia and Herzegovina | 49 | 21.2 | +27.7 | +131% | 18 | 94.4% |
| Albania | 255 | 36.6 | +45.5 | +124% | 170 | 88.2% |
| Moldova | 19 | 27.7 | +29.1 | +105% | 21 | 90.5% |
| South Africa | 100 | 8.6 | +6.1 | +71% | 94 | 74.5% |
| Uzbekistan | 403 | 13.8 | +9.3 | +67% | 153 | 76.5% |
| Fiji | 69 | 7.2 | +4.8 | +67% | 58 | 75.9% |
| Kenya | 45 | 9.2 | +5.4 | +59% | 32 | 87.5% |
| Montenegro | 133 | 20.6 | +11.5 | +56% | 109 | 74.3% |
| Namibia | 5 | 0.4 | **-0.1** | -25% | 10 | 40.0% |

*Addressable* is schools with at least five tests, mostly on 5 GHz-capable
hardware, mostly observed on 2.4 GHz. *Gain* is the within-school median
throughput change moving to 5 GHz, in Mb/s. *Evidence* is how many schools that
estimate rests on — below about 20 the figure is indicative only, which is why
Belize (18), Botswana (15), Malawi (11), Lesotho (3), Trinidad (4) and
Kazakhstan (1) are omitted here despite large apparent gains.

**A low use-of-negotiated-rate ratio does not mean the radio is irrelevant.**
That inference is wrong and the within-school test is what shows it: Malawi
runs at 0.05 of its negotiated rate yet gains 11.1 Mb/s on 5 GHz, more than
doubling what its schools get. The negotiated rate is a headline PHY figure; on
2.4 GHz, interference, retries and collisions push actual throughput far below
it, so the band can be impairing a school even when the rate suggests headroom.
Read `median_ratio` as a description of the gap between headline and delivered,
not as a diagnosis of its cause.

Namibia is the one country measured to gain nothing: 0.4 Mb/s now, -0.1 Mb/s
from a band change, 40% of schools faster on 5 GHz. Whatever limits those
schools is not the radio.

### The capability columns, read with that caveat

`capable_hw_pct` is the share of tests on hardware that can use 5 GHz (84%
overall); `capable_on_24ghz_pct` is the share of that hardware observed on
2.4 GHz anyway (64%, above 85% in Kazakhstan, Zambia, Malawi and Uzbekistan).
That gap is real, but on the evidence above it is only worth acting on in the
first two rows of the table — elsewhere the band would change the negotiated
rate and not the result.

`wifi_model` names the **client's** adapter, not the access point, so "capable
hardware" means a capable laptop. A school never reaching 5 GHz may have an
access point that cannot offer it, making the fix procurement rather than
configuration; the measurement cannot separate those.

The radio's negotiated rate correlates with throughput across schools in 12 of
21 countries with enough schools to test; signal strength does so in 3.
