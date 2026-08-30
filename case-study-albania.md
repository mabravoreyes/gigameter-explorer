# Albania — three routes out of one country

Albania has no domestic M-Lab server. Every school measurement crosses the
border, and **96.7% of a school's round-trip time accrues outside the country**:
a median 1.05 ms domestic against 34.38 ms international. Nothing a national
operator does to its own network can touch the other 97%.

The destination is Podgorica, about 130 km from Tirana.

## Three routes, one destination, 14x apart

| route | schools | share of paths | median RTT | median path | throughput |
|---|---:|---:|---:|---:|---:|
| **AL → ME** (direct) | 19 | 3.4% | **4.0 ms** | 56 km | 83.8 Mb/s |
| AL → RS → HR → ME | 283 | 72.4% | 27.1 ms | 1,250 km | 72.8 Mb/s |
| AL → IT/DE/AT → … → ME | 81 | ~10% | **54.9 ms** | 1,880-5,481 km | 31.1 Mb/s |

Same country, same destination, same period. A school on the direct path
reaches Podgorica in 4 ms; a school on the European path takes 55 ms and less
than half the throughput.

## It is the operator's choice, not the school's geography

The route follows the provider almost perfectly:

| operator | direct | via RS/HR | via IT/DE/AT |
|---|---:|---:|---:|
| **I.B.C shpk** | **94.7%** | 3.9% | 1.4% |
| Abissnet | 0% | 91.4% | 7.9% |
| Albtelecom | 0% | 87.3% | 10.6% |
| Albanian Telecommunications Union | 0% | 88.8% | 4.5% |
| **Telekom Albania** | 0% | 0.8% | **96.9%** |
| Albanian Satellite Communications | 0% | 13.5% | 82.9% |

Four small providers — I.B.C, Mobitel, VIVO, Meshnet — peer directly into
Montenegro and deliver 4 ms. **Telekom Albania sends 96.9% of its school
traffic through Italy, Germany or Austria.** The country's regional
interconnection is being done by its smallest operators.

Within one operator the same pattern holds and rules out school-side
explanations: Abissnet reaches the same server in 26.9 ms via Cogent and
65.2 ms via Arelion, across 46,820 traces.

## The inequality is a routing inequality

| | schools | median RTT | median throughput |
|---|---:|---:|---:|
| Urban | 178 | 27.5 ms | **84.9 Mb/s** |
| Rural | 212 | 32.9 ms | **36.6 Mb/s** |

Rural schools get **43% of the throughput** urban schools get. And the regional
pattern is not about distance — it is about which route the region's provider
uses:

| region | schools | median RTT | % on the European route |
|---|---:|---:|---:|
| Dibër | 9 | **59.2 ms** | **88.9%** |
| Vlorë | 6 | 48.6 ms | 50.0% |
| Fier | 24 | 40.0 ms | 58.3% |
| Tiranë | 211 | 27.5 ms | 15.2% |
| Shkodër | 13 | 25.9 ms | 7.7% |
| Lezhë | 7 | **3.8 ms** | 14.3% |

Dibër, the poorest and most mountainous region, is not slow because it is
remote — Podgorica is closer to Dibër than to Tirana. It is slow because 89% of
its school traffic is routed through western Europe. Of the eight worst-served
schools, six are rural and five are Telekom Albania schools on the European
route.

## It improved March to May, then gave much of it back

The Giga Meter campaign began in March 2026 and the fleet grew from 99 schools
to 856 by May, so nothing can be read off a country-level series. The
comparison below is restricted to schools present in **both** months of each
pair — the balanced panel — which removes the arrival of new schools.

**The endpoint chosen changes the answer, so all of them are shown:**

| pair | schools | start → end | change | improved |
|---|---:|---|---:|---:|
| Mar → Apr | 95 | 48.4 → 44.2 ms | -8.7% | 75.8% |
| Mar → May | 93 | 48.3 → 25.1 ms | **-48.0%** | 92.5% |
| Mar → Jun | 84 | 48.7 → 24.9 ms | **-48.8%** | 94.0% |
| **Mar → Jul** | 42 | 45.9 → 41.5 ms | **-9.7%** | 83.3% |
| Apr → May | 282 | 41.7 → 26.6 ms | -36.1% | 84.8% |
| **Apr → Jun** | **253** | 41.7 → 26.3 ms | **-37.0%** | 79.4% |
| Apr → Jul | 162 | 40.1 → 34.4 ms | -14.3% | 59.9% |
| May → Jun | 670 | 28.3 → 29.9 ms | +5.4% | 48.1% |
| **Jun → Jul** | 470 | 29.9 → 36.0 ms | **+20.3%** | 32.3% |

The honest arc is **improvement to May, flat to June, deterioration into July**.
Median school RTT falls from 48 ms to 25 ms and then rises again to 36 ms. On
the June-to-July pair only 32.3% of the same 470 schools improved. A March-to-
June headline of -48.8% is real but it is the most flattering pair available,
and March-to-July on the same basis is -9.7%.

Two cautions on the July reversal. It coincides with the end of the school
year, when volume falls 58% mid-month and the panel changes character; and the
schools still testing in July may not be typical. But this is a balanced panel,
so it is the *same* schools getting slower, not different ones.

**April is the better starting point for any claim.** March had only 99 schools
measuring, so a March-anchored panel is 42-95 schools; April gives 253 for the
same April-to-June window, with the finding intact at -37.0% and 79.4% of
schools improving.

### What drove the improvement

Restricting to schools with enough *completed* traces in both months — needed
because classifying a route requires a path that reaches the client, and only
53.1% of attributed traces complete — gives 60 schools for March to June, a
strict subset of the 84 above. On that subset the improvement is slightly
stronger (-52.6%, 98.3% improving), and it decomposes into two mechanisms:

* **44 of the 60 never changed route** and still gained a median 21.2 ms: the
  Serbia/Croatia path itself sped up, from 42.6 ms in March to 26.2 ms in May.
* **16 moved off the European route** onto the regional one, gaining a median
  37.9 ms.

A third thing appeared alongside: the direct AL → ME path did not exist in
March, carried 1.3% of paths in April, and 8.5% by July. New regional
interconnection is happening and is measurable — and it is the one part of this
picture that did not reverse.

## Why the routes are long in the first place

Across 1.16 million observed hops, **83 cross a known internet exchange point —
0.007%**. There is effectively no exchange-point interconnection on these
paths. With nowhere regional to hand traffic off, it goes to a Tier-1 and
travels. Two countries gate the common route: Montenegro is entered from
Croatia on 93.4% of paths, and Croatia from Serbia on 81.9%.

## A second, cheaper lever

Independent of routing, 255 Albanian schools run 5 GHz-capable hardware on the
2.4 GHz band. Schools seen on both bands gain a within-school median
**+45.5 Mb/s** moving to 5 GHz, and 88.2% are faster on it (170 schools of
evidence). Albania is one of the countries where this is worth doing — it runs
at 0.22 of its negotiated radio rate, against 0.01-0.06 for countries where the
radio is nowhere near limiting.

## This one can be checked

**82.4% of Albanian school traffic sits in a network with a live RIPE Atlas
probe** — 117 registered, 28 connected, 3 anchors. A follow-up can test these
routes toward destinations schools actually use, rather than only toward an
M-Lab server. For comparison, Namibia's equivalent finding sits at 6.8%
coverage and cannot be independently confirmed.

## What would undercut this

* **One vantage point.** 96% of traces terminate at Podgorica. These are routes
  to that server, not to the internet in general — the direct path's 4 ms says
  Montenegro is close, not that those schools are fast to everything.
* **Counts run over a larger population than the published country pages.** The
  school-IP filter is applied downstream of these files; the UUID join used here
  lands about 17% high against the published Belize figure.
* **Client location is not verified.** Median 0.21 km from the registered
  school, but 52 km at the 90th percentile and 1,015 tests beyond 10 km. Some
  "school" measurements were not taken at the school.
* **The March-anchored panel is small** — 84 schools, because only 99 were
  measuring that month — and it is also the most flattering endpoint. Use the
  April-anchored panel (253 schools, -37.0%) for anything load-bearing, and
  state the July reversal alongside it.
* **Regional cells are small.** Dibër is 9 schools and Lezhë 7; treat those
  medians as indicative.
