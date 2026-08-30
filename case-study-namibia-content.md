# Namibia — where the M-Lab server sits close to where the content is

A traceroute study measures the path to an M-Lab server. Whether that path
resembles the one a school actually uses depends on whether the content a school
opens is served from anywhere near that server. In Sri Lanka it is not. In
Namibia it largely is, and that makes Namibia's traceroute findings unusually
transferable.

## The setup

Namibia has no domestic M-Lab server. Its traffic is measured against `cpt01`
in **Cape Town, South Africa**, at a median 42 ms. The question is whether
school-relevant content is also served from South Africa.

Measured 2026-08-30 from three RIPE Atlas probes in Namibian school-serving
networks, with five probes in South African school-serving networks as an
in-country reference (measurements 205924290-99, data in `data/atlas/`).

## What Namibian schools actually reach, and where

| target | served from | Namibia RTT | South Africa RTT |
|---|---|---:|---:|
| **Google Classroom** | Google, **Johannesburg** (`…jnb…1e100.net`) | 18-60 ms | 20.9 ms |
| **YouTube** | Google, same fabric | 19-150 ms | 23.6 ms |
| **Claude** | Anthropic / Cloudflare | 18-70 ms | 4.2 ms |
| Khan Academy | Fastly | 55-179 ms | **3.4 ms** |
| Wikipedia | **Amsterdam** (`esams`) / Marseille (`drmrs`) | 144-230 ms | 177.1 ms |

The AS paths are short. Namibian networks reach Google in **one hop** —
`Paratus → Google`, `MTC → Google` — and Anthropic in one or two. There is no
transit chain to speak of for the largest content sources.

## Why this makes Namibia the useful case

Google Classroom, YouTube and Claude are reached at **18-60 ms**, and Namibia's
M-Lab server sits at **42 ms** in the same country the Google endpoint resolves
into. The measurement path and the content path land in the same place, so a
finding about the route to Cape Town says something about the route to the
content.

Compare Sri Lanka, where the two diverge completely: the M-Lab servers are in
India at ~175 ms, the national learning platform is hosted domestically and
reached in 3-8 ms, and Wikipedia comes from Singapore at 79 ms. No statement
about the Indian path transfers to either.

**This is what makes the Namibian split-routing finding worth presenting.**
Telecom Namibia reaches Cape Town at 35 ms over its own network and at 190 ms
via Cogent — and Cape Town is where the content is. The 155 ms is not an
artefact of measuring toward an arbitrary server.

## What does not transfer

Two of the five targets are served from Europe, not Africa. Wikipedia resolves
to Amsterdam for Namibian probes and Marseille for South African ones, at
144-230 ms; Khan Academy sits behind Fastly, which South African probes reach
in **3.4 ms** and Namibian probes in 55-179 ms. So the claim is "much of the
heaviest content", not "all content".

## The gap between Namibia and South Africa is the second finding

South African schools reach Fastly in 3.4 ms and Anthropic in 4.2 ms. Namibian
schools reach the same services in 55-179 ms and 18-70 ms. The content is on the
continent; Namibia is not consistently getting to it.

Within Namibia the spread is wide — one probe reaches Google in 18 ms and
another in 58 ms, and on Khan Academy the same two differ by 134 ms and 55 ms
depending on whether the path goes via NTT America or the West Indian Ocean
Cable Company. Which Namibian network a school buys from decides its content
latency more than the content's location does.

## Limits

* Three Namibian probes, in networks carrying about 7% of school traceroutes.
  Telecom Namibia, which carries 93%, has no live probe — so the operator at
  the centre of the traceroute finding cannot be measured this way.
* Probes are in the right networks but not in schools.
* Five targets, chosen for coverage of the heaviest school-relevant traffic;
  national LMS platforms are not included here.
