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

## Why this is a clean comparison

**Within one operator, one month, one destination.** Sri Lanka Telecom carries
55.6% of school traceroutes. In July 2026 it sent 32.0% of its traffic direct
and 63.7% through Europe:

| SLT, July 2026 | traces | median RTT |
|---|---:|---:|
| direct LK → IN | 14,883 | **55.6 ms** |
| via Europe | 29,691 | **189.2 ms** |

Same network, same month, same destination country: **3.4x the latency**, on
44,574 traces. The access network, the schools and the contract are held
constant; only the route changes.

**And one operator already does it.** Hutchison Telecommunications Lanka routes
100% direct. This is not a limit of Sri Lankan infrastructure.

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
