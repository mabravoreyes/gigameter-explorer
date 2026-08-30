# RIPE Atlas measurements

One-off measurements run from this repository, kept with their measurement IDs
so a result can be traced back to the probes that produced it.

## `lk_ethaksalawa_*` — Sri Lanka's national e-learning platform

Measurement IDs 205905591 (traceroute), 205905592 (ping), 205905593 (DNS),
run 2026-08-30 against `e-thaksalawa.moe.gov.lk` (122.255.40.216) from 11
probes chosen to match the networks that carry school traffic:

* **AS9329 Sri Lanka Telecom** — 55.6% of school traceroutes — probes 35547,
  64124, 65075, 1014699
* **AS18001 Dialog** — 29.6% — probes 64185, 64382, 64629
* **AS38229 LEARN**, the national education and research network — probes 7596,
  7605, 51241, 60433

Two of Sri Lanka's five school-serving networks have no live probe at all
(IS Group AS45356 at 10.7% of traces, Hutchison AS132447) and Etisalat's two
probes are disconnected, so this covers about 85% of school traffic and cannot
speak for the rest.
