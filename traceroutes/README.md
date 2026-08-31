# Traceroute exploration

Exploratory work on where school traffic actually goes, kept separate from the
numbered Giga Meter pipeline at the repository root. Nothing here is part of
that pipeline: the notebooks read its outputs and the committed traceroute
exports, and none of the `00`-`06` notebooks depend on anything in this folder.

| Notebook | Question |
|---|---|
| `internet_geography.ipynb` | Which networks carry a country's school traffic, through which countries, and what the routing costs in latency |
| `atlas_probe_coverage.ipynb` | Whether RIPE Atlas has a probe in the networks that serve schools — i.e. whether a finding can be checked independently |
| `starlink.ipynb` | Starlink as a school ISP: adoption, routing against terrestrial, and where it wins and loses |

Each notebook resolves the repository root in its first cell and works from
there, so it runs the same whether launched from this folder or from the root.

## Notes and case studies

* `report-parity.md` — the 15 sections of the published GIGA Traceroute Studies
  country pages, mapped against what these notebooks reproduce, approximate, or
  cannot do.
* `case-study-sri-lanka.md` — the strongest case-study candidate found: schools
  reaching servers in India by way of Singapore, France and the United States,
  with the direct route observable in the same data.

## Data

Committed exports and derived tables live in `data/traceroutes/`; helpers in
`helpers/` (`load_traceroutes`, `fetch_traceroutes`, `join_schools`,
`starlink`, `atlas_probes`, `wifi_analysis`, `traceroute_profiles`). Interactive
figures are written to `outputs/`.
