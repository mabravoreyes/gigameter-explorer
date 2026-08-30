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

## A routing decision, visible as it happens

Sri Lanka Telecom re-routed during the period, and it shows within that
operator alone rather than in the country mix:

| SLT share of its own completed paths | Feb | Mar | Apr | May | Jun | **Jul** |
|---|---:|---:|---:|---:|---:|---:|
| via Singapore | 71.8 | 74.4 | 76.8 | 72.4 | 65.7 | **2.1** |
| via Europe | 2.4 | 2.2 | 1.6 | 3.6 | 1.9 | **63.7** |
| direct | 10.0 | 9.3 | 9.0 | 10.5 | 24.2 | **32.0** |

The country-level effect was a trade: median RTT rose from 117.2 ms in June to
169.1 ms in July, while median throughput more than doubled, 9.5 to 20.8 Mb/s.
A capacity decision taken at the cost of latency — which is the wrong trade for
video lessons and interactive tools, and is invisible to procurement written in
Mb/s.

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
