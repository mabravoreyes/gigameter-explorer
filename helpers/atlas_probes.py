"""
RIPE Atlas probe coverage, against the networks that actually serve schools.

RIPE Atlas is the obvious way to extend a traceroute finding: probes can be
pointed at any target on demand, where the M-Lab exports only show the path to
whichever server the school's client chose. That only works where Atlas has a
probe in the network under study, and this module checks whether it does.

Probe discovery needs no API key — only creating measurements does.

    import sys; sys.path.insert(0, 'helpers')
    from atlas_probes import fetch_probes, probe_inventory, coverage_against_schools

    probes = probe_inventory('NA')
    coverage_against_schools('NA', probes)
"""

from __future__ import annotations

import json
import urllib.request

import pandas as pd

_API = "https://atlas.ripe.net/api/v2/probes/"

# A probe that is not currently connected cannot be measured from, however
# healthy its history. Atlas reports several dead states; only this one counts.
_LIVE = "Connected"


def fetch_probes(country_iso2: str, page_size: int = 500) -> list[dict]:
    """Every probe ever registered in a country, whatever its current state."""
    results, url = [], f"{_API}?country_code={country_iso2.upper()}&format=json&page_size={page_size}"
    while url:
        with urllib.request.urlopen(url, timeout=60) as response:
            page = json.load(response)
        results.extend(page.get("results", []))
        url = page.get("next")
    return results


def probe_inventory(country_iso2: str, probes: list[dict] | None = None) -> pd.DataFrame:
    """One row per probe: network, prefix, status, and whether it is usable now."""
    probes = probes if probes is not None else fetch_probes(country_iso2)
    rows = []
    for probe in probes:
        status = probe.get("status", {}).get("name")
        rows.append({
            "probe_id": probe.get("id"),
            "asn_v4": probe.get("asn_v4"),
            "prefix_v4": probe.get("prefix_v4"),
            "status": status,
            "connected": status == _LIVE,
            "is_anchor": bool(probe.get("is_anchor")),
            "is_public": bool(probe.get("is_public")),
            "tags": ", ".join(sorted(t["slug"] for t in probe.get("tags", []))
                              if probe.get("tags") else []),
        })
    return pd.DataFrame(rows)


def coverage_against_schools(country_iso2: str, inventory: pd.DataFrame,
                             traceroutes: pd.DataFrame | None = None,
                             data_root=None) -> pd.DataFrame:
    """
    Join the networks carrying school traffic to the probes available in them.

    The question is not how many probes a country has but whether they sit in
    the networks the schools use. A country can look covered and still have no
    probe in the operator that carries most of its schools, which makes the
    finding unverifiable by an independent measurement.
    """
    if traceroutes is None:
        from load_traceroutes import load_traceroutes
        traceroutes = load_traceroutes(country_iso2, data_root=data_root)

    schools = (traceroutes.groupby(["src_asn", "src_asn_name"])
                          .size().rename("traces").reset_index())
    schools["trace_pct"] = (100 * schools["traces"] / schools["traces"].sum()).round(1)

    live = inventory[inventory["connected"]]
    counts = inventory.groupby("asn_v4").size().rename("probes_registered")
    live_counts = live.groupby("asn_v4").size().rename("probes_connected")

    out = (schools.merge(counts, left_on="src_asn", right_index=True, how="left")
                  .merge(live_counts, left_on="src_asn", right_index=True, how="left"))
    out[["probes_registered", "probes_connected"]] = (
        out[["probes_registered", "probes_connected"]].fillna(0).astype(int))
    out["measurable"] = out["probes_connected"] > 0
    return out.sort_values("traces", ascending=False).reset_index(drop=True)


def coverage_summary(coverage: pd.DataFrame) -> dict:
    """How much of a country's school traffic sits in a network Atlas can reach."""
    measurable = coverage[coverage["measurable"]]
    return {
        "school_asns": len(coverage),
        "asns_with_live_probe": int(coverage["measurable"].sum()),
        "traces_measurable_pct": round(float(measurable["trace_pct"].sum()), 1),
        "largest_asn": coverage.iloc[0]["src_asn_name"] if len(coverage) else None,
        "largest_asn_pct": float(coverage.iloc[0]["trace_pct"]) if len(coverage) else None,
        "largest_asn_measurable": bool(coverage.iloc[0]["measurable"]) if len(coverage) else None,
    }
