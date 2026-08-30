"""
Interactive Plotly views of Starlink school performance.

Two charts, both written to `outputs/` as self-contained HTML that loads
plotly.js from a CDN, so the files stay small enough to open and to mail.

    python helpers/starlink_charts.py            # rebuild both

`school_panel()` pulls one row per school, month and access technology from
Giga Meter and caches it, so the charts rebuild offline afterwards.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _ROOT / "cache" / "school_month_panel.parquet"
_OUT = _ROOT / "outputs"

STARLINK_BLUE, TERRESTRIAL_GREY = "#277aff", "#989898"


def _names() -> dict:
    ref = json.loads((_ROOT / "helpers" / "country_reference.json").read_text())
    return {k: v["name"] for k, v in ref.items()}


def school_panel(start: str = "2025-01-01", cursor=None,
                 use_cached: bool = True) -> pd.DataFrame:
    """One row per school, month and access technology, from `start` onwards."""
    if use_cached and _CACHE.exists():
        return pd.read_parquet(_CACHE)

    import sys
    sys.path.insert(0, str(_ROOT / "helpers"))
    from starlink import STARLINK_SQL
    if cursor is None:
        from load_measurements import get_trino_cursor
        cursor = get_trino_cursor()

    cursor.execute(f"""
        SELECT iso3_code, school_id_giga, school_name, school_area_type,
               date_trunc('month', date) AS month,
               CASE WHEN {STARLINK_SQL} THEN 'Starlink' ELSE 'Terrestrial' END AS kind,
               count(*) AS tests,
               approx_percentile(download_speed, 0.5) AS dl,
               approx_percentile(CAST(latency AS DOUBLE), 0.5) AS rtt,
               approx_percentile(CAST(packet_loss_rate AS DOUBLE), 0.5) AS loss
        FROM all_gigameter_measurement_data
        WHERE date >= DATE '{start}'
          AND download_speed IS NOT NULL AND latency IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5, 6
    """)
    panel = pd.DataFrame(cursor.fetchall(),
                         columns=[d[0] for d in cursor.description])
    panel["month"] = pd.to_datetime(panel["month"]).dt.strftime("%Y-%m")
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(_CACHE, index=False)
    return panel


def _prepare(panel: pd.DataFrame, min_tests: int = 3) -> pd.DataFrame:
    names = _names()
    d = panel.copy()
    for col in ("dl", "rtt", "loss"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d["loss"] = d["loss"] * 100
    d = d[d["tests"] >= min_tests].dropna(subset=["dl", "rtt"])
    d = d[d["iso3_code"].notna()]
    d["country"] = d["iso3_code"].map(lambda c: names.get(c, c))
    d["school"] = d["school_name"].fillna(d["school_id_giga"].str[:8])
    # Null area types would be dropped by a later groupby, taking whole
    # countries with them.
    d["school_area_type"] = d["school_area_type"].fillna("unknown")
    return d


def _write(fig, path: Path, title: str) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    html = pio.to_html(fig, include_plotlyjs="cdn", full_html=True,
                       config={"displaylogo": False})
    html = html.replace("<head>", f"<head><title>{title}</title>", 1)
    path.write_text(html)


def chart_starlink_over_time(panel: pd.DataFrame) -> Path:
    """
    Every Starlink school, latency against throughput, animated by month.

    Log axes on both: school throughput spans three orders of magnitude, and on
    linear axes the slow majority collapses onto the origin.
    """
    d = _prepare(panel)
    sl = d[d["kind"] == "Starlink"].copy()

    # Plotly Express builds one trace per colour category from the FIRST frame
    # only. Countries whose first Starlink school appears later are dropped
    # silently, legend and all — which removed 12 of 17 here, Malawi included.
    # Padding every country into every frame with null coordinates registers
    # the trace without drawing anything.
    months = sorted(sl["month"].unique())
    countries = sorted(sl["country"].unique())
    grid = pd.MultiIndex.from_product([countries, months],
                                      names=["country", "month"]).to_frame(index=False)
    present = set(zip(sl["country"], sl["month"]))
    padding = grid[[t not in present for t in zip(grid["country"], grid["month"])]].copy()
    padding["school_id_giga"] = "_pad_" + padding["country"]
    padding["school"] = ""
    for column in ("rtt", "dl", "loss"):
        padding[column] = float("nan")
    padding["tests"] = 0          # marker size rejects NaN; null x/y hides the point
    for column in ("iso3_code", "school_area_type"):
        padding[column] = ""
    sl = pd.concat([sl, padding], ignore_index=True)
    sl = sl.sort_values(["month", "country"])

    fig = px.scatter(
        sl, x="rtt", y="dl",
        animation_frame="month", animation_group="school_id_giga",
        color="country", size="tests", size_max=26, hover_name="school",
        hover_data={"iso3_code": True, "school_area_type": True, "tests": True,
                    "loss": ":.2f", "rtt": ":.0f", "dl": ":.1f",
                    "month": False, "country": False},
        log_x=True, log_y=True, range_x=[5, 3000], range_y=[0.05, 600],
        labels={"rtt": "median RTT (ms) — log scale",
                "dl": "median download (Mb/s) — log scale",
                "country": "Country", "loss": "loss %",
                "school_area_type": "area", "tests": "tests"},
        title="Schools on Starlink: latency against throughput, 2025 to date"
              "<br><sup>One point per school per month · size = tests that month "
              "· press play</sup>",
    )
    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.6)")))
    fig.update_layout(height=740, template="plotly_white",
                      font=dict(family="Open Sans, Helvetica, Arial, sans-serif", size=12),
                      title=dict(font=dict(size=18)),
                      legend=dict(title="Country", x=1.01, y=1),
                      margin=dict(l=70, r=180, t=100, b=70))
    fig.add_vline(x=100, line_dash="dot", line_color="rgba(0,0,0,0.25)")
    fig.add_hline(y=10, line_dash="dot", line_color="rgba(0,0,0,0.25)")
    fig.add_annotation(x=0.02, y=0.98, xref="paper", yref="paper", showarrow=False,
                       text="<b>fast and responsive</b>",
                       font=dict(size=11, color=STARLINK_BLUE), align="left")
    fig.add_annotation(x=0.98, y=0.03, xref="paper", yref="paper", showarrow=False,
                       text="<b>slow and laggy</b>",
                       font=dict(size=11, color="#ed1c24"), align="right")
    if fig.layout.updatemenus:
        button = fig.layout.updatemenus[0].buttons[0]
        button.args[1]["frame"]["duration"] = 900
        button.args[1]["transition"]["duration"] = 400

    path = _OUT / "starlink_schools_rtt_download.html"
    _write(fig, path, "Starlink schools — RTT vs download")
    return path


def chart_starlink_vs_terrestrial(panel: pd.DataFrame, min_starlink_schools: int = 5) -> Path:
    """
    Starlink schools against every other school in the same country, one panel each.

    One point per school rather than per school-month: this is a school-level
    comparison, the first chart carries the time dimension, and per-month points
    made the file eight times larger without adding to the question.
    """
    d = _prepare(panel)
    counts = (d[d["kind"] == "Starlink"].groupby("iso3_code")["school_id_giga"].nunique())
    d = d[d["iso3_code"].isin(counts[counts >= min_starlink_schools].index)].copy()

    d = (d.groupby(["iso3_code", "country", "school_id_giga", "school",
                    "school_area_type", "kind"])
           .agg(rtt=("rtt", "median"), dl=("dl", "median"), loss=("loss", "median"),
                tests=("tests", "sum"), months=("month", "nunique"))
           .reset_index())

    order = (d[d["kind"] == "Starlink"].groupby("country")["school_id_giga"]
             .nunique().sort_values(ascending=False).index.tolist())
    columns = 3
    fig = px.scatter(
        d, x="rtt", y="dl", color="kind",
        facet_col="country", facet_col_wrap=columns,
        category_orders={"country": order, "kind": ["Terrestrial", "Starlink"]},
        color_discrete_map={"Starlink": STARLINK_BLUE, "Terrestrial": TERRESTRIAL_GREY},
        opacity=0.55, size="tests", size_max=18, hover_name="school",
        hover_data={"months": True, "school_area_type": True, "tests": True,
                    "loss": ":.2f", "rtt": ":.0f", "dl": ":.1f",
                    "country": False, "kind": False},
        log_x=True, log_y=True,
        labels={"rtt": "median RTT (ms)", "dl": "median download (Mb/s)",
                "kind": "", "loss": "loss %", "school_area_type": "area"},
        title="Starlink against every other school in the same country"
              "<br><sup>One point per school, median over 2025 to date · size = tests "
              "· countries with at least five Starlink schools</sup>",
    )
    rows = math.ceil(len(order) / columns)
    fig.update_layout(height=300 * rows + 140, template="plotly_white",
                      font=dict(family="Open Sans, Helvetica, Arial, sans-serif", size=11),
                      title=dict(font=dict(size=18)),
                      legend=dict(orientation="h", y=1.04, x=0.5, xanchor="center",
                                  itemsizing="constant"),
                      margin=dict(l=70, r=40, t=140, b=60))
    fig.for_each_annotation(lambda a: a.update(text="<b>" + a.text.split("=")[-1] + "</b>",
                                               font=dict(size=13)))
    fig.update_traces(marker=dict(line=dict(width=0.3, color="rgba(255,255,255,0.5)")))
    fig.update_xaxes(showticklabels=True, matches=None)
    fig.update_yaxes(showticklabels=True, matches=None)

    path = _OUT / "starlink_vs_terrestrial_by_country.html"
    _write(fig, path, "Starlink vs terrestrial by country")
    return path


if __name__ == "__main__":
    panel = school_panel()
    for builder in (chart_starlink_over_time, chart_starlink_vs_terrestrial):
        written = builder(panel)
        print(f"wrote {written.relative_to(_ROOT)} "
              f"({written.stat().st_size / 1e6:.2f} MB)")
