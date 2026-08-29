# Albania traceroutes (M-Lab)

Monthly traceroute exports for Albania, from
<https://giga-traceroutes.measurementlab.net/country/al.html>.
`manifest.json` records the source, row counts and a sha256 per file.

| File | Rows | Coverage |
|---|---:|---|
| `giga_AL_2026-02.parquet` | 0 | published empty — 25 columns, no `__index_level_0__` |
| `giga_AL_2026-03.parquet` | 6,278 | 2026-03-01 → 03-31 (27 days) |
| `giga_AL_2026-04.parquet` | 26,009 | 2026-04-01 → 04-30 |
| `giga_AL_2026-05.parquet` | 50,910 | 2026-05-01 → 05-31 (30 days) |
| `giga_AL_2026-06.parquet` | 40,381 | 2026-06-01 → 06-30 (30 days) |
| `giga_AL_2026-07.parquet` | 17,337 | 2026-07-01 → 07-31 (30 days) |

2026-02 is an empty export; every other month from the campaign's March start is
present, so March→July is a continuous monthly series.

## Loading

`pd.read_parquet()` fails on these files: they carry BigQuery `dbdate` pandas
metadata that pandas cannot parse. Use the helper, which reads through pyarrow
and skips the empty month:

```python
import sys; sys.path.insert(0, 'helpers')
from load_traceroutes import load_traceroutes, hop_frame, upstream_adjacency
tr = load_traceroutes('AL')
```

## Direction of measurement

M-Lab runs the traceroute **from its server towards the client**, so a path in
`forward_updated_node_details` starts at `dst_asn` (the server's host network)
and ends at `src_asn` (the client's network in Albania):

* `src_*` — the **client**: ASN, name, city, coordinates.
* `dst_*` — the **M-Lab server**: site code (`tgd01` = Podgorica), host ASN.
* `is_reaching_dst_asn` — the trace completed all the way into the *client's*
  ASN. The "destination" in that name is the traceroute's target, i.e. the
  client. Verified on 2026-07: all 6,362 flagged rows begin at `dst_asn`, and
  6,338 end at `src_asn`; none of the 10,975 unflagged rows do.

This matters for any transit claim. Every trace starts at the same server, so
the early hops describe *M-Lab's* connectivity and are common to every Albanian
ISP — Hrvatski Telekom appears on most paths for that reason, not because every
Albanian ISP buys from it. Only the hops adjacent to the client distinguish one
provider's upstream from another's, which is what `upstream_adjacency()` takes.

## Scope

These are school measurements by construction. The published methodology is
explicit: *"We filter each dataset to known school IP ranges."* The 7,789
distinct client IPs across 481 /24s in June 2026 are therefore dynamic
addressing across Albania's school estate, not 7,789 distinct premises.

The timing independently agrees, which is worth keeping as a check on the
filter: 60% of traces fall in the weekday 08:00-15:59 window against the 24% a
uniform clock would put there, the hourly profile peaks at 08:00-09:00 and
decays through the school day rather than rising into the evening as
residential traffic does, and weekend days carry 7-8% of traces each against
16-18% for each weekday.

The same signature dates the series to the school calendar, which constrains
what months can be compared. March through June hold the school-hours peak
(58-66% of traces in the weekday window). July does not: the profile flattens
to 48.6%, the weekend share rises, and daily volume falls 58% between the first
and second half of the month as the school year ends. **July is not a like-for-
like month against March-June** — a trend line drawn through it is measuring
the summer holiday as much as anything else.

The filter identifies schools as a set of IP ranges, not individually, so the
data still carries no school identity. To attach one — and turn trace shares
into school counts — join `id`, the NDT UUID (e.g.
`ndt-2zjb9_1781008606_0000000000265E39`), against `uuid` in the Giga Meter
measurements, the same key the traceroute cell of `meter_explorer_02.ipynb`
uses.

## Other caveats

* `reverse_updated_node_details` is populated on only ~20% of rows (3,422 of
  17,337 in July); the forward path is the reliable one.
* Unresolved (`*`) hops appear with `addr = '*'`, a null ASN and `rtts = -1.0`.
  `hop_frame()` flags these as `responded = False`.
* `src_asn_name` is null for some networks even when the ASN is known; the hop
  annotations name them, and `upstream_adjacency()` fills from there.
* AS42313 appears as `Albtelecom Sh.a.` in `src_asn_name` and as
  `ONE ALBANIA SH.A.` in hop annotations — the same operator under its
  pre- and post-merger names.
* `dst_site` is overwhelmingly `tgd01` (Podgorica): 96% of July traces. The
  handful routed to `sof01`/`sof02` (Sofia), `beg01` (Belgrade) and `ath03`
  (Athens) are not comparable baselines for distance or RTT.
