# Figures

`albania.html` — the Albania traceroute figures, as a single self-contained
page. Open it directly in a browser; there are no external dependencies beyond
the Google Fonts stylesheet, and it renders without that too.

## Editing

Everything is in the one file. The data sits in a `const D = {...}` block near
the top of the `<script>` at the bottom, separated from the drawing code, so
numbers can be corrected without touching any SVG:

| key | figure |
|---|---|
| `D.routes` | three routes, per-school medians |
| `D.ops` | operator route mix (each school's split, averaged) |
| `D.flow` | Abissnet's two upstreams |
| `D.ndt` | what the longer route costs |
| `D.regions` | region scatter |
| `D.area` | rural / urban |
| `D.arc` | balanced panel, 67 schools |
| `D.multi` | four NDT7 measures indexed to April |
| `D.direct` | share of schools on the direct route |

Colours are CSS custom properties on `:root` — `--r1` / `--r2` / `--r3` are the
route ramp, light to dark by latency. Each is redefined for dark mode in two
places (`prefers-color-scheme` and `[data-theme="dark"]`); change all three or
one theme will fall out of step.

## Regenerating the numbers

The figures are computed by the analysis in `traceroutes/internet_geography.ipynb` and
`helpers/`. `case-study-albania.md` states each figure's population, weighting
and caveats, and is the place to check before quoting anything.

Two rules the page depends on: every figure uses only school-attributed traces
(94,315 of the 140,915 in the export), and school-level figures are computed one
school at a time, because the 25 busiest schools carry 51% of the traces.

## Publishing

The published copy lives at
<https://claude.ai/code/artifact/120ce15f-d7da-4a35-822e-fe2f8d65e8bd>.
It is private until shared from the page's own share menu.
