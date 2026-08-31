# Albania — three routes out of one country

**Scope.** The published export is every NDT client in Albania, not a school
set: 140,915 traces, of which **94,315 (66.9%) are attributable to a
Giga-registered school** by test ID. Every figure below uses that school subset
only. The excluded third sits on the same networks — Albtelecom, Abissnet,
ABCOM and Telekom Albania lead it — so including it shifts the country
aggregates slightly (median RTT 28.7 ms on schools against 32.3 on everything).

Albania has no domestic M-Lab server. Every school measurement crosses the
border, and **96% of a school's round-trip time accrues outside the country**:
a median 1.15 ms domestic against 30.4 ms international. Nothing a national
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

Within one operator the same pattern holds, and it can be pushed further than a
group comparison. Abissnet's two upstreams serve largely the same estate — 183
of its 226 schools appear on both, and only one school is exclusive to Arelion
— so each school can be compared against itself:

| Abissnet, 129 schools with >=5 traces on both upstreams | |
|---|---|
| median via Cogent | **26.0 ms** |
| median via Arelion | **64.0 ms** |
| median within-school difference | **+37.0 ms** |
| schools slower on Arelion | **128 of 129 (99%)** |
| Wilcoxon signed-rank | p = 5.7e-23 |

The school, its access network, its contract, its location and its destination
are all held constant. Only the route changes, and 99% of schools are slower on
the longer one. This is the strongest causal claim available in the dataset.

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

## What the route does and does not affect

Every Albanian measurement is NDT7 with download, upload, latency and loss
populated, so the routing claim can be tested on more than round-trip time.
Holding the operator fixed — Abissnet, which carries 49,000 traces across both
its upstreams — separates what the route causes from what the operator does:

| Abissnet via | traces | latency | download | upload | loss | path |
|---|---:|---:|---:|---:|---:|---:|
| Cogent | 39,715 | **27 ms** | 75.7 Mb/s | 65.6 Mb/s | 4.8% | 1,250 km |
| Arelion | 3,295 | **64 ms** | 73.9 Mb/s | 53.3 Mb/s | 6.6% | 3,030 km |

**The route costs latency, and barely touches download.** 2.4x the latency, a
23% upload penalty, and a download difference of 2% that is noise. The
cross-sectional throughput gap between routes — 85 Mb/s on the direct path
against 30 on the European one — is therefore mostly *which operators take
which route*, not the route itself.

That narrows the claim and sharpens it. Routing is a latency problem, and
latency is what governs video lessons, live classes and anything interactive.
It is not a bandwidth problem, and presenting it as one invites a correct
rebuttal.

**Two consequences.** The rural/urban gap is a *different* problem: rural
schools trail on download (35.7 against 84.3 Mb/s) and upload (19.1 against
72.3) but only slightly on latency (33 against 28 ms). That is access capacity,
not routing, and it will not be fixed by peering.

**Retransmission is a loss measure, but a confounded one.** The field labelled
`packet_loss_rate` is `s2c_bytes_retrans / s2c_bytes_sent`, verified on 100% of
112,607 Albanian rows — TCP's response to loss on the download path. It is a
reasonable loss proxy, byte-weighted rather than packet-counted, and an upper
bound because reordering and early timeouts also trigger retransmission. It is
not a different quantity from loss, and an earlier version of this note was
wrong to say so.

What it *is* is two signals mixed together, and Albania separates them cleanly.

**Between routes it reads as path quality:**

| route | download | retransmission | latency |
|---|---:|---:|---:|
| direct | 86.2 Mb/s | **0.04%** | 3 ms |
| via Serbia/Croatia | 75.0 Mb/s | 4.91% | 27 ms |
| via western Europe | 47.5 Mb/s | **5.87%** | 61 ms |

The fastest route has the least retransmission and the slowest has the most, on
*lower* throughput. If this were purely an artefact of a saturating test, the
fastest route would show the most. It does not, so between paths the field
carries genuine signal.

**Within one route it reads as saturation.** Holding Abissnet and the
Serbia/Croatia route fixed, across 197 schools, retransmission correlates
+0.33 with download and −0.29 with latency:

| Abissnet, one route | retransmission | download | latency |
|---|---:|---:|---:|
| least-retransmitting quarter | 0.05% | 33.3 Mb/s | 28 ms |
| most-retransmitting quarter | **13.60%** | **94.5 Mb/s** | 25 ms |

The schools retransmitting most are the *fastest*. A school on a fat pipe
pushes until it finds the bottleneck buffer; a school on a thin pipe never gets
there. Within a path, this measures test intensity, not service quality.

**So: usable between paths, not for ranking schools.** Comparing routes or
countries on retransmission is defensible when throughput does not move against
it. Saying "Albanian schools lose 3.8% of packets" is not — that national
median mixes both effects, and the schools contributing most to it are the
best-connected ones.

## The reversal is latency-only

Re-running the balanced panel of 67 schools on every NDT7 metric shows the July
reversal is specific to latency:

| balanced panel, 67 schools | Apr | May | Jun | Jul |
|---|---:|---:|---:|---:|
| latency (ms) | 41.0 | 25.0 | 25.0 | **38.5** |
| download (Mb/s) | 74.7 | 85.3 | 84.9 | **88.7** |
| upload (Mb/s) | 62.9 | 83.9 | 76.3 | 78.2 |
| retransmission (%) | 5.24 | 4.85 | 5.11 | 3.77 |

Download is at its best in July, in the same month latency is worst.
Retransmission also falls, which is the direction path quality would move but
the opposite of what rising throughput would produce under saturation — the two
effects work against each other here, so read it as weakly favourable rather
than as a clean result. The schools did not get worse; their *routing* did, which is
consistent with the European share rising through June and July. Stated as "the
gains reversed" the claim is wrong. Stated as "the latency gains reversed while
capacity kept improving" it is right, and it is a cleaner argument for treating
routing as its own policy object.

## Why the routes are long in the first place

Across 1.04 million observed school hops, **59 cross a known internet exchange
point — 0.006%**. There is effectively no exchange-point interconnection on these
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
