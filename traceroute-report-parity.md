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
| 07 | Country Traversal Graph | **Q8, Q8b, Q8c** | Reproduced: ordered paths, unavoidable transit, gated entry, transition matrix |
| 08 | International Transit Concentration | **Q3-Q3d** | Two of three egress views and chokepoint coverage reproduced; the third (first foreign-*registered* AS) needs an ASN-to-country registry not in these files |
| 09 | Loss Rate Analysis | Q6 | Has loss median; **missing** loss by AS-path-length and by distance bucket |
| 10 | Per-School Performance | Q7 partial | Q7 counts schools correctly via UUID rather than IP, avoiding the distortion the report flags in its own version |
| 11 | School-Level Study | **Q7, Q7b** | Join implemented via Trino (`helpers/join_schools.py`); routing-vs-performance correlations still missing |
| 12 | Wi-Fi and School Performance | **Q7c-Q7e**, `wifi_profiles.csv` | Reproduced, and extended to all 23 countries with Wi-Fi data; security (WPA2) is the one attribute the measurement table does not carry |
| 13 | Temporal Patterns | Q2, Q2b | Has hour-of-day and day-of-week; **missing** RTT/throughput/loss by hour and day |
| 14 | Path Quality | Q6, Annex | Has reachability; **missing** geographic detour ratio and path stability |
| 15 | RTT Decomposition | **Q6-Q6c** | Reproduced: domestic/international split plus attribution per transit ASN and per country |

## Worth stealing

One construct is still worth adding; the other three are now implemented.

**Geographic detour ratio** (§14). Path distance over school-to-server
great-circle distance. Belize July: mean 2.56, and 4.00 median for `mex04`
against 1.01 for `mex01`. It turns "the path is long" into "the path is 4x
longer than it needs to be", which is the version that survives a policy
conversation.

**The one remaining egress view** (§08). First foreign-*registered* AS — the
ownership crossing rather than the geographic one. Needs an ASN-to-registration-
country table; nothing in these files carries it. Q3d computes the other two,
and for Albania hand-off and border crossing are the same operator on 92.6% of
paths, so the gap that view would expose is small here.

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

**Wi-Fi (§12).** Reproduced through the Giga Meter join rather than the
traceroute files. Belize July: median client distance from the registered
school 0.10 km exactly matching the report, p90 45.6 km against 46, generation
802.11ac at 71.4% of schools against 70%. The section's actual finding survives
too — the negotiated radio rate predicts throughput (rho +0.73, p 0.002 here;
+0.71, p 0.021 published) while signal strength does not.

Albania then showed why that conclusion must be derived and not asserted: there
*both* correlations are significant (radio +0.43, signal +0.16), so the notebook
picks its reading from the data rather than repeating Belize's.

**The school filter is the UUID join, but does not reproduce their count.**
Filtering the parquet to rows whose `id` matches a Giga Meter
`measurement_uuid` for the month is the right mechanism and is what Q7 does. It
lands high: 1,040 rows against the published 889, or 984 restricting to
measurements that passed validity, and 80 distinct client IPs against their 28.
The most likely cause is that the measurement table has been backfilled since
the report was generated, so more UUIDs match now than did then; a curated
IP-range list applied on top would also explain it. Either way, counts here run
over a larger population than the site's, which is the systematic reason every
magnitude in this document sits a few points high or low.


**RTT attribution (§15).** The strongest match of the three. Belize July, AS174:
median 69.7 ms here against the report's 69.7 exactly; mean 79.3 against 77.0.
By country per hop, MX is 4.18 ms against their 4.2.

This one exposed a definitional trap worth keeping. Their per-ASN table is
milliseconds *per traceroute*; their per-country table is *per hop*. Reading
one as the other makes a country appear to add 77 ms when it adds 9 ms per hop.
`rtt_attribution()` reports both columns for that reason.

**Transition matrix (§07).** BZ→MX 46.7% against 49.2%, BZ→US 38.6% against
43.0%, US→MX 54.3% against 50.8% — all tracking, all short by the school
filter.

**Egress views (§08).** First-transit HHI 0.666 against 0.785, first-out-of-
country 0.713 against 0.838. Both views rank the same operator top (AS23520)
and both agree the border view is more concentrated than the hand-off view,
which is the qualitative finding.
