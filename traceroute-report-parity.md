# Published country reports vs `meter_traceroutes_07.ipynb`

The GIGA Traceroute Studies site publishes a report per country-month in 15
sections. This maps them against the notebook, so it is clear what is
reproduced, what is approximated, and what cannot be done from the published
parquet alone. Section content is taken from the Belize July 2026 report.

## The gate on all of it

The published reports run on the **school-filtered** subset; the parquet is the
unfiltered input. Belize July 2026: 889 school measurements from 28 school IPs,
against 1,316 rows and 204 client IPs in the file. Every figure below that the
notebook computes is therefore over a different, larger population than the
same figure on the site, and the two will not match exactly. Reproducing the
filter needs the `id` (NDT UUID) join to the Giga Meter API, which needs Trino.

A worked example of the gap, same month, same metric: the report's egress HHI
is 0.785 with AS23520 at 88.0% of tests; the notebook's method on the
unfiltered file finds the same top egress AS at 77.2% and HHI 0.637. The
finding survives, the magnitude does not.

## Section by section

| # | Published section | Notebook | Gap |
|---|---|---|---|
| 01 | How to Read This Report | Q0 + Annex | Direction verified from data rather than asserted |
| 02 | Dataset Overview | Part 0, Q1 | No school-IP counts — needs the filter |
| 03 | Network Topology Graphs | — | **Missing.** AS-level and AS-city graphs, node/edge counts, force-directed and Sankey views |
| 04 | Average Path Length: Local vs International | Q5 | Has distance and countries crossed; **missing** IP-hop and AS-hop counts, and the local/international split |
| 05 | IXP Crossing Analysis | Q5c | Equivalent (both find ~0 IXP crossings) |
| 06 | Transit Country Dependency | Q5, Q5b | Has countries traversed; **missing** the IP-geolocation vs AS-registration split |
| 07 | Country Traversal Graph | **Q8, Q8b** | Ordered paths, unavoidable transit and gated entry reproduced; transition matrix still missing |
| 08 | International Transit Concentration | Q3, Q3b, Q3c | Closest match. Notebook's upstream-adjacency ≈ their "first observed transit"; **missing** their other two egress views and chokepoint coverage |
| 09 | Loss Rate Analysis | Q6 | Has loss median; **missing** loss by AS-path-length and by distance bucket |
| 10 | Per-School Performance | Q7 partial | Q7 counts schools correctly via UUID rather than IP, avoiding the distortion the report flags in its own version |
| 11 | School-Level Study | **Q7, Q7b** | Join implemented via Trino (`helpers/join_schools.py`); routing-vs-performance correlations still missing |
| 12 | Wi-Fi and School Performance | — | **Not possible here.** Wi-Fi fields are Giga Meter, not in the traceroute parquet |
| 13 | Temporal Patterns | Q2, Q2b | Has hour-of-day and day-of-week; **missing** RTT/throughput/loss by hour and day |
| 14 | Path Quality | Q6, Annex | Has reachability; **missing** geographic detour ratio and path stability |
| 15 | RTT Decomposition | Q6, Q6b | Notebook splits domestic vs international; the report attributes per transit ASN and per country |

## Worth stealing

Two of their constructs are still worth adding; a third (entry structure) is
now implemented as Q8.

**Geographic detour ratio** (§14). Path distance over school-to-server
great-circle distance. Belize July: mean 2.56, and 4.00 median for `mex04`
against 1.01 for `mex01`. It turns "the path is long" into "the path is 4x
longer than it needs to be", which is the version that survives a policy
conversation.

**Three egress views** (§08). First observed transit AS, first AS outside the
country, first foreign-registered AS. The notebook computes only the first.
The gap between the physical border crossing and the ownership crossing is
itself the finding.

**RTT attributed per transit AS** (§15). Belize July: AS174 adds a mean 77.0 ms
per traceroute. The notebook's domestic/international split is coarser; naming
the AS is what makes it actionable.

## Their framing rules

Carried into the notebook and the data README:

* *"Loss is not reachability."* Loss is end-to-end from the NDT transfer;
  reachability is whether traceroute probes arrived. A transfer can show zero
  loss while its traceroute stops short.
* *"Thresholds are relative."* Their "underserved", "high" and "low" cuts come
  from each country's own distribution and do not compare across countries —
  the same warning `country_profiles.csv` carries for distance and RTT.
* *"Routing is often asymmetric, so these findings need not hold for traffic
  leaving the school."* The reverse path is present on only ~16% of rows, and
  the report measures 0.0% forward/reverse AS-path match for Belize.


## Validation against the Belize report

Two checks where their published figures let the method be tested.

**Entry structure (§07).** Unavoidable transit reproduces exactly — MX, on
every measured path. Mexico's main predecessor is US on 50.6% of paths against
their 51%. The ordered paths track but do not match: BZ→MX 42.8% against their
49.2%, BZ→US→MX 34.9% against 43.0%. The gap is the school filter (1,316 rows
here against their 889) plus geolocation noise, which adds re-entrant paths
like BZ→MX→US→MX that their cleaner subset does not show.

**Transit concentration (§08).** Same top egress AS identified (AS23520), at
77.2% and HHI 0.637 here against their 88.0% and 0.785 — again the filter.

**The school filter itself could not be reproduced.** Their "known school IP
ranges" is a curated list: for Belize July it keeps 889 rows from 28 IPs, where
the measurement table exposes 102 IPs of which 69 intersect the traceroute
file. Filtering the traceroutes to those 69 keeps 1,038 rows, not 889. The UUID
join keeps 1,040 across 32 schools. Since the reports themselves warn that
IP-keyed school figures are distorted, the UUID join is the better instrument
regardless, and Q7 uses it.
