# Sri Lanka — the route that already exists

Every M-Lab server serving Sri Lanka sits in India: Chennai (`maa01`, `maa02`,
`maa03`) and Kochi (`cok138754`). Colombo to Chennai is about 1,300 km. The
median measured path is **6,174 km at 174.9 ms**, and 96.5% of that latency
accrues outside the country — 6.6 ms domestic against 185.4 ms international.

## The finding

The direct route is not hypothetical. It is in the same data, carrying 28,091
completed traces:

| route | share | median RTT | median path | median throughput |
|---|---:|---:|---:|---:|
| **LK → IN** | 16.0% | **74.8 ms** | 2,613 km | 17.7 Mb/s |
| LK → SG → IN | 39.1% | 187.8 ms | 5,694 km | 7.5 Mb/s |
| LK → FR → IN | 18.2% | 187.4 ms | **16,746 km** | 38.7 Mb/s |
| LK → US → SG → IN | 2.1% | 202.9 ms | **32,129 km** | 25.1 Mb/s |
| LK → US → IN | 1.3% | 210.3 ms | 29,564 km | 24.6 Mb/s |

To reach a server across the Palk Strait, 84% of school traffic takes a longer
route than one already in use — a fifth of it through Europe or North America.

## Why this is a clean comparison — with the server held fixed

An earlier draft compared routes without holding the destination server
constant, and that was not safe. Sri Lanka's four servers differ enormously in
their own right: `maa03` runs a median 98.7 ms, `cok138754` 167.4, `maa01`
198.6 and `maa02` 338.5. Any route comparison that lets the server vary is
partly measuring server choice.

It also hid a second problem. The `LK → IN` country sequence is not one path.
Decomposed by AS path, it holds at least seven, spanning **54 ms to 414 ms**:

| AS path inside "LK → IN" | share | RTT | throughput |
|---|---:|---:|---:|
| Kerala Vision → Weblink → Sri Lanka Telecom | 46.1% | **54.3 ms** | 44.3 Mb/s |
| Reliance Jio → Dialog | 18.0% | 84.7 ms | 6.1 Mb/s |
| Kerala Vision → Dialog | 17.7% | 104.5 ms | 6.7 Mb/s |
| Reliance Jio → Sri Lanka Telecom | 6.7% | 191.1 ms | 27.1 Mb/s |
| Bharti Airtel → Sri Lanka Telecom | 2.2% | **413.9 ms** | 19.6 Mb/s |

A country sequence is too coarse to carry a finding. The comparison below fixes
**one operator, one server, one month**.

**Sri Lanka Telecom to Kochi (`cok138754`), July 2026:**

| route | traces | median RTT | median throughput |
|---|---:|---:|---:|
| direct LK → IN | 14,205 | **55.1 ms** | 42.6 Mb/s |
| via Europe | 29,672 | **189.2 ms** | 38.9 Mb/s |

**3.4x the latency for no throughput gain** — 42.6 against 38.9 Mb/s, so this is
not a capacity trade. The same contrast appears at `maa01`, where SLT runs
61.1 ms direct against 202.0 via Singapore.

## But it is one operator's problem, not the country's

Dialog, which carries a comparable share, shows almost no route effect once the
server is fixed — and at Kochi the indirect path is *faster*:

| Dialog | direct | via Singapore |
|---|---:|---:|
| at `maa03` | 85.2 ms | 96.7 ms |
| at `cok138754` | 104.6 ms | **82.6 ms** |

So "Sri Lankan schools are routed the long way round" is wrong as a national
claim. **Sri Lanka Telecom's routing is the finding**, and it matters because
SLT carries 55.6% of school traceroutes. Hutchison routes 100% direct, which
shows the path is available.

## Counted in schools

3,252 of the 3,391 schools measuring in the period carry attributed
traceroutes — the largest school base of any country in this dataset. By the
route each school predominantly takes:

| dominant route | schools | share |
|---|---:|---:|
| via Europe | 1,272 | 42.3% |
| via Singapore | 900 | 29.9% |
| **direct** | **603** | **20.0%** |
| via US | 12 | 0.4% |

Roughly 2,200 schools take a slower path to India than 603 other Sri Lankan
schools demonstrably get.

## What every operator does

The route is not a national property. Each operator makes its own choice, and
they differ more than the country figures suggest:

| operator | share of completed | route mix | RTT | throughput |
|---|---:|---|---:|---:|
| **Dialog Telekom** | 53.6% | 78.5% via SG · 11.7% direct | 113.5 / **86.4** ms | 6.2 / 6.4 Mb/s |
| **Sri Lanka Telecom** | 42.4% | 43.3% via EU · 25.5% via SG · **25.3% direct** | 189.8 / 202.0 / **57.9** ms | 38.3 / 26.1 / **36.0** Mb/s |
| **IS Group** | 4.0% | 99.1% via SG | 93.3 ms | 7.5 Mb/s |
| **Hutchison** | small | **100% direct** | 99.6 ms | — |
| Etisalat | small | 52.4% via EU · 47.6% via SG | — | — |

Two things follow that a country-level reading would miss.

**The same route performs differently for different operators.** LK → SG → IN
costs Dialog 113.5 ms and Sri Lanka Telecom 202.0 ms — the same country
sequence, 1.8x apart. The route shape is not the whole explanation; how each
operator provisions it matters as much.

**The operators are making opposite trades.** Dialog is the low-latency,
low-throughput network (86-113 ms at 6 Mb/s); Sri Lanka Telecom is the
high-latency, high-throughput one (58-210 ms at 26-38 Mb/s). A school's
experience depends on which of those its provider chose, and neither is
strictly better — they suit different things.

Sri Lanka Telecom is where the spread lives: its own direct path runs 57.9 ms
against 189.8 through Europe and 210.3 through the United States. It is the
operator with both the best and the worst routes in the country.

## The July shift — and what it is not

Sri Lanka Telecom re-routed during the period, visible within that operator
rather than in the country mix:

| SLT share of its own completed paths | Feb | Mar | Apr | May | Jun | **Jul** |
|---|---:|---:|---:|---:|---:|---:|
| via Singapore | 71.8 | 74.4 | 76.8 | 72.4 | 65.7 | **2.1** |
| via Europe | 2.4 | 2.2 | 1.6 | 3.6 | 1.9 | **63.7** |
| direct | 10.0 | 9.3 | 9.0 | 10.5 | 24.2 | **32.0** |

**The country median RTT rose from 117.2 ms in June to 169.1 in July, and that
rise is an artefact of who was measuring.** Every operator improved on both
measures across those months:

| operator | June RTT | July RTT | June Mb/s | July Mb/s |
|---|---:|---:|---:|---:|
| Dialog Telekom | 101.4 | **83.1** | 6.2 | 7.8 |
| Sri Lanka Telecom | 204.7 | **180.1** | 24.0 | 38.6 |
| IS Group | 93.2 | 93.4 | 7.3 | 7.5 |

What changed is the mix: Sri Lanka Telecom, the slower network, went from 35.0%
of completed paths in June to 63.1% in July while Dialog fell from 64.9% to
27.9%. Holding June's operator mix and applying July's within-operator
performance gives **117.1 ms** — indistinguishable from June's 117.2. The
country got no slower; more of it was measured through the slow operator.

An earlier draft of this note read the rise as a capacity purchase paid for in
latency. It was Simpson's paradox, and the same trap waits for any
country-level trend line drawn over a panel whose composition is still moving —
which, five months into a rollout, this one is.

## Who is on the slow path

Attributing traceroutes to schools by NDT UUID, over schools with at least five
completed attributed paths:

| | schools | median RTT |
|---|---:|---:|
| mostly direct | 431 | **57.6 ms** |
| mostly indirect | **1,981** | **184.3 ms** |

**1,981 schools sit on the slower path, paying a median 127 ms.** Restricting to
the clean comparison — Sri Lanka Telecom at Kochi, schools with five or more
tests — 1,134 schools route mostly through Europe at 188.1 ms while 416 route
mostly direct at 53.5 ms.

## It is also a geographic equity question

Routing is not evenly distributed. Across 64 education zones with at least 15
schools, the share of traffic taking the direct path correlates with median
latency at **rho = -0.62 (p < 0.0001)** — and within Sri Lanka Telecom alone,
across 53 zones, at **rho = -0.77 (p < 0.0001)**. It is not an artefact of
which operator serves where.

The north is worst served. Jaffna sits at 192.7 ms with 5.2% of its traffic
direct; Valikamam 194.1 ms at 6.8%; Vadamaradchi 197.8 ms at 7.1%. Against
Akuressa at 84.0 ms with 34.0% direct, and Maho at 96.8 ms with 32.1%.

| province | schools | direct | median RTT |
|---|---:|---:|---:|
| North Western | 556 | 25.0% | 166.9 ms |
| Southern | 466 | 16.7% | 178.5 ms |
| Northern | 485 | 13.4% | 189.9 ms |
| North Central | 215 | 8.0% | 191.6 ms |

## Controlling for fleet growth

The panel is not stable, so nothing about "over time" can be read off a
country-level series. The Giga Meter fleet in Sri Lanka went from 1,191 schools
in February to **3,191 in July** — a 2.3x jump in the final month alone, and the
reason the operator mix moved.

`balanced_panel()` compares only the schools present in **both** months, which
removes the arrival of new schools from the comparison:

| Sri Lanka | schools A → B | both | naive | balanced | composition |
|---|---|---:|---:|---:|---:|
| Jun → Jul | 1,002 → 2,779 | 953 | -10.2% | **-8.6%** | -1.6 pp |
| Feb → Jul | 953 → 2,779 | 837 | -12.3% | **-9.9%** | -2.4 pp |
| May → Jun | 1,166 → 1,002 | 893 | +0.9% | -0.8% | +1.7 pp |

**On the schools that were there for both, latency fell.** 80.0% of the 953
schools common to June and July improved, by a median 31.3 ms. Over the full
period, 65.2% of 837 schools improved by a median 32.0 ms.

Note this cuts against the completed-path country median reported above, which
rose from 117.2 to 169.1 ms across the same two months. Both are computed
correctly; they are different populations. The country median is over completed
traceroute paths, whose operator mix moved sharply; the balanced panel is over
schools, holding the schools fixed. **The balanced figure is the one to quote
about schools**, because it is the only one that answers what a school
experienced.

## What makes this the strongest candidate

* **Largest evidence base**: 318,551 traces, 3,252 schools, six complete months.
* **The counterfactual is measured, not modelled** — 603 schools already get the
  fast path.
* **Verifiable**: 85.2% of school traffic sits in networks with a live RIPE
  Atlas probe (`ripeatlas_08.ipynb`), against 6.8% for Namibia. A follow-up can
  test these routes toward destinations schools actually use.
* **A second, cheaper lever**: 1,170 schools run 5 GHz-capable hardware on
  2.4 GHz, worth a within-school median +25.4 Mb/s.

## The routing finding does not describe the national learning platform

Measured directly, 2026-08-30, from RIPE Atlas probes in the same networks that
carry school traffic (measurement 205905591; data in `data/atlas/`).

`e-thaksalawa.moe.gov.lk` — the Ministry of Education's e-learning platform —
resolves to **122.255.40.216, inside Dialog's own network (AS18001)**. Every
probe resolves it to that single address, so there is no split-horizon or
regional variation to account for.

**Every network reaches it domestically, in single-digit milliseconds:**

| probe network | last responding hop | RTT |
|---|---|---:|
| Dialog AS18001 | `10.121.17.202` (inside Dialog) | **2.8 ms** |
| LEARN AS38229 | `125.214.162.158` → Dialog | **8.3 ms** |
| Sri Lanka Telecom AS9329 | `10.121.17.202` (inside Dialog) | **8.2 ms** |

Sri Lanka Telecom and LEARN both enter Dialog over the same two hops,
`218.100.61.13` and `125.214.162.158`, at 7.7-8.4 ms. **There is no foreign
detour.** Sri Lanka Telecom schools pay about 5 ms more than Dialog schools to
reach the platform, and that is the whole penalty.

**So the 189 ms via-Europe path is about reaching an M-Lab server in India, and
does not describe how schools reach the content they actually use.** The
national platform is hosted in-country and reached in-country. Any framing that
implies Sri Lankan schoolchildren wait 189 ms for their own ministry's learning
material would be wrong.

What the M-Lab finding does still support: Sri Lanka Telecom's *international*
routing is poor, which bears on everything hosted abroad — and most of what a
school uses beyond the national platform is hosted abroad. That is a narrower
claim than the traceroute data alone appears to make, and it is the one to
present.

**A limit on this measurement.** The host answers neither ping nor traceroute:
no probe got an ICMP reply and no trace completed. The figures above are to the
last responding hop inside Dialog, not to the server. They establish that the
*path* is domestic and short; they say nothing about how the application
performs, which traceroute cannot see.

## Can we say Sri Lanka Telecom's international routing is poor? No.

The M-Lab data shows Sri Lanka Telecom reaching Indian test servers at 189 ms
via Europe where a 55 ms path exists. It is tempting to generalise that to
"SLT's international routing is poor". Measured directly against fixed
destinations, that generalisation is false.

Median minimum RTT, 2026-08-30, from probes in each network (measurements
205913617-25, data in `data/atlas/`):

| network | Sinhala Wikipedia | Mumbai anchor | Singapore anchor |
|---|---:|---:|---:|
| **Sri Lanka Telecom** | 78.9 ms | **26.6 ms** | **40.8 ms** |
| **Dialog** | **39.6 ms** | 32.9 ms | 80.6 ms |
| LEARN | 92.3 ms | 29.9 ms | 79.7 ms |

**Sri Lanka Telecom is the fastest of the three to India, and twice as fast as
Dialog to Singapore.** It is slower only to Wikipedia. Dialog is the mirror
image: best to Wikipedia, worst to Singapore. Neither operator has "poor
international routing"; they have different interconnection.

### It is peering, not routing

Every probe's resolver returns the same Wikipedia address —
`103.102.166.224`, `text-lb.eqsin.wikimedia.org`, Wikimedia's **Singapore**
datacentre — so all three networks are aiming at the same place. The AS paths
show why they arrive differently:

| from | AS path to Wikimedia | RTT |
|---|---|---:|
| Dialog | AS18001 → AS14907 Wikimedia | **39.3 ms** |
| Sri Lanka Telecom | AS45489 SLT Global → AS14907 Wikimedia | 87.6 ms |
| LEARN | AS38229 → AS18001 Dialog → AS14907 | 119.8 ms |

Both large operators peer with Wikimedia directly, one AS hop. Dialog's
interconnection with Wikimedia is evidently in or near Singapore; Sri Lanka
Telecom's is not, because SLT reaches the Singapore *anchor* in 40.8 ms while
taking 87.6 ms to a Wikimedia server in the same city. **The gap is where each
operator meets that specific content network, not how either reaches the
region.** LEARN, the national education network, has no direct route at all and
transits Dialog to get there — 119.8 ms for the network built to serve
education.

### What this does to the M-Lab finding

Sri Lanka Telecom reaches Mumbai in **26.6 ms**. Whatever produces its 189 ms
path to the Indian M-Lab servers, it is not an inability to reach India. The
M-Lab result is about the route to those particular destination networks — and
possibly about the return direction, since M-Lab traces run server-to-client
while the RTT is round-trip. It should be presented as a finding about **those
paths**, not about SLT's international connectivity.

The claim that survives all of this is narrower and more useful: **which content
a Sri Lankan school reaches quickly depends on which operator it buys from, and
the two large operators are good at opposite things.** A school on Dialog gets
Wikipedia at 39 ms and Singapore at 81; a school on SLT gets Wikipedia at 79 and
Singapore at 41. That is a procurement-relevant fact that no bandwidth figure
would reveal — and LEARN, the network schools might expect to be best served by,
is worst on two of the three.

## Has the network shape changed, independent of fleet growth?

Mostly no. The apparent transformation is a new test server, not a re-route.

Taking the **170 schools present in all six months** — so fleet growth cannot
contribute — the route mix looks like it collapses in July:

| balanced panel | Feb | Mar | Apr | May | Jun | Jul |
|---|---:|---:|---:|---:|---:|---:|
| direct | 6.6 | 6.5 | 5.4 | 4.9 | 15.8 | **52.7** |
| via Singapore | 84.5 | 85.6 | 88.7 | 88.4 | 75.9 | **20.3** |
| median IP hops | 14 | 14 | 14 | 14 | 12 | **9** |
| median countries | 3 | 3 | 3 | 3 | 3 | **2** |
| median RTT | 207.8 | 208.9 | 180.7 | 115.0 | 194.6 | **74.7** |

But the server mix moves with it. Those same schools were tested against
Chennai (`maa01`, `maa03`) until June and against **Kochi (`cok138754`) for
88.7% of July**. A closer server produces a shorter path; that is not the
network changing.

**Holding the server fixed, the dominant path is static.** At `maa01`, the same
170 schools route via Singapore on 99.5-100% of paths in every month from
February to July. Six months, no structural change.

The two changes that appeared to survive that control do not survive a closer
one. **Nothing measurable about Sri Lanka's network changed over the period;
M-Lab's server fleet did.**

Each server sits in exactly one hosting network, one to one:

| server | hosted by | US-transiting share |
|---|---|---:|
| `maa01` Chennai | Tata Communications | 8.8% |
| `maa03` Chennai | Reliance Jio | 9.7% |
| `maa02` Chennai | Bharti Airtel | 24.8% |
| `cok138754` Kochi | Kerala Vision | **0.4%** |

So "the United States path was eliminated" is a change in which server was being
measured, not in how Sri Lanka routes. The Kochi server — which barely transits
the US — appears in July and takes 88.7% of the traffic, displacing servers that
transit the US on 9-25% of paths. The country-wide US share falls from 12.1% to
1.3% without any Sri Lankan network doing anything.

The intermediary makes it concrete. Sri Lanka Telecom's US-crossing paths ran
through **Telstra International**, and within `maa01` that path is *still there*
in July, unchanged:

| SLT at `maa01` | Feb | Mar | Apr | May | Jun | Jul |
|---|---:|---:|---:|---:|---:|---:|
| via Telstra | 79.8% | 85.3% | 81.3% | 89.3% | 86.9% | **88.7%** |
| median RTT | 200.8 | 203.0 | 197.4 | 200.3 | 203.6 | **198.7** |

Six months, no change. What moved was the destination: across all of Sri Lanka
Telecom's paths, Kerala Vision goes from 0% of traces before July to 95.1% in
July, while Tata falls from 77% to 3.0%.

**And 17.1% of the panel changed provider.** 29 of 170 schools switched
dominant ISP at least once; 23 differ between February and July, 17 of them
moving from Dialog to Sri Lanka Telecom. School-level churn of that size moves
any aggregate on its own, and it is invisible unless the panel is held fixed.

This is the third temporal finding in this case study to dissolve under
control, after the July "capacity trade" (operator mix) and the July route
collapse (server mix). The pattern is consistent and worth stating plainly:
**M-Lab's own infrastructure changed more over these six months than Sri
Lanka's networks did**, and any trend drawn from this data without fixing the
destination server is measuring M-Lab. The cross-sectional findings — one
operator, one server, one month — are unaffected.

One oddity worth flagging rather than explaining away: at `maa01` the median
path length jumps from 5,662 km in February to 11,129 in May while RTT *falls*
from 214 to 114 ms. A longer path that is faster suggests the distance figure —
summed from hop geolocation — is unreliable over that stretch, not that physics
changed.

## The server change moved Giga Meter's own numbers

This is the finding with the most direct consequence for reporting.

Taking the **1,123 schools that measured against Chennai before July and
against Kochi in July**, with at least five tests on each side, their reported
NDT results improved substantially:

| | Chennai (pre-July) | Kochi (July) | change | improved |
|---|---:|---:|---:|---:|
| median RTT | 200.4 ms | **180.8 ms** | -9.8% | 84.0% |
| median throughput | 24.5 Mb/s | **30.1 Mb/s** | +23.1% | 69.4% |
| median loss | 0.00 | 0.00 | — | — |

Wilcoxon p = 3.6e-114 on RTT and 8.6e-47 on throughput. **Nothing changed at
these schools.** Their operator did not change, their route to a fixed server
did not change, and the balanced panel at `maa01` shows flat RTT across all six
months. M-Lab added a server in Kochi.

The cleanest form of the control holds schools, month *and* connection fixed and
varies only the server. For the 769 schools that measured against both servers
**within July**:

| July only, same schools | Chennai | Kochi | delta |
|---|---:|---:|---:|
| median RTT | 191.1 ms | 183.9 ms | **-7.9 ms** (p = 1.3e-24) |
| median throughput | 30.4 Mb/s | 35.7 Mb/s | **+2.4 Mb/s** (p = 3.1e-18) |

**A country-level improvement in Giga Meter's Sri Lanka figures for July is
therefore not evidence that Sri Lankan school connectivity improved.** Anyone
reading the reported series without knowing the server fleet changed would draw
the wrong conclusion.

### And the benefit is unequal

Which of the two Kochi paths a school landed on decides almost everything:

| July path | schools | RTT before | RTT after | throughput before | after |
|---|---:|---:|---:|---:|---:|
| **Weblink, direct within India** | 188 | 198.8 ms | **54.1 ms** | 30.3 | **51.2 Mb/s** |
| **Bharti Airtel, via Europe** | 781 | 203.7 ms | 186.0 ms | 28.0 | 33.2 Mb/s |
| other | 154 | 194.3 ms | 79.0 ms | 9.9 | 9.2 Mb/s |

188 schools saw latency fall by **73%**; the 781 on the Bharti path saw 9%. The
aggregate improvement is real arithmetic over a benefit almost none of them
shared equally.

### The Europe detour is real, and it is Bharti Airtel's

Hop RTTs confirm the geolocation rather than contradicting it. On the slow path
the jump happens **inside Bharti Airtel**, between its Indian ingress and its
handoff to Sri Lanka Telecom:

| ttl | country | network | RTT |
|---:|---|---|---:|
| 1 | IN | Kerala Vision | 0.0 ms |
| 2 | IN | Bharti Airtel | 1.9 ms |
| 3 | IN | Bharti Airtel | **166.0 ms** |
| 4 | NL | Sri Lanka Telecom | 162.0 ms |
| 5 | LK | Sri Lanka Telecom | 187.9 ms |

164 ms accrues within one AS before the handoff, which is consistent with a
genuine long-haul detour and not with a mislabelled router. The equivalent
Weblink path reaches Sri Lanka Telecom at 46 ms having never left India.

So the mechanism is **where Bharti Airtel and Sri Lanka Telecom interconnect** —
in northern Europe rather than in South Asia. It is not, as an earlier draft
had it, a failing of Sri Lanka Telecom's international routing: Sri Lanka
Telecom reaches Mumbai in 26.6 ms when measured directly.

## What to check before presenting

* **The "direct" class is not stable across months.** SLT's direct paths read
  68.7 ms in February, 184-192 ms from March to June, then 55.6 ms in July. A
  single `LK → IN` country sequence is hiding more than one physical path, and
  the July figure should not be quoted as though it held all period.
* **Counts run over a larger population than the published country pages** —
  the school-IP filter is applied downstream of these files.
* **Client location is not verified**: schools are attributed by NDT UUID, but
  22.6 client IPs per school is high even for dynamic addressing.
* Completion is 51.7%, so the route shares describe completed paths.
* **The destination is an M-Lab server, not the content schools use.** The
  section above measures the national platform directly and finds no foreign
  detour; do not let the two be conflated.
* Two of five school-serving networks have no live Atlas probe (IS Group at
  10.7% of traces, Hutchison), so the direct measurement covers about 85% of
  school traffic.
* The Atlas probes are not in schools. They sit in the same networks, which is
  what makes the operator comparison valid, but a school's own last mile is not
  measured here.
* Three or four probes per network is a small sample; the within-network spread
  was tight (SLT 78.4-79.4 ms to Wikipedia) but LEARN ranged 76-120 ms.
* The London anchor returned no replies and is excluded.
