"""Build the public, static version of the dashboard.

    uv run --env-file .env python dashboard/build_static.py

Runs the same governed MetricFlow metrics as the Streamlit app, then writes a single
self-contained page to docs/index.html. GitHub Pages serves that file: it never sleeps,
costs nothing, needs no warehouse credentials, and keeps working after the warehouse
is switched off. Charts stay interactive (tooltips) because Vega-Lite runs in the browser.
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

import altair as alt
from metrics_client import metric_catalog, query_metrics
from transforms import complete_weeks, humans_vs_bots

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "index.html"

TITLE = "GitHub Community Health Analytics"
SUBTITLE = (
    "How active are the communities behind 64 popular open-source data tools, "
    "and how much of the work is done by bots?"
)
REPO_URL = "https://github.com/ParitoshVyawahare/oss-pulse"
DATA_START = dt.date(2026, 8, 1)

HUMAN, BOT, TEAL, INK, MUTED, GRID = (
    "#2563EB",
    "#F59E0B",
    "#0EA5E9",
    "#0F172A",
    "#64748B",
    "#EEF2F7",
)

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 52 52">'
    '<rect width="52" height="52" rx="14" fill="#2563EB"/>'
    '<polyline points="11,34 20,24 28,30 40,16" fill="none" stroke="#FFFFFF" '
    'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="40" cy="16" r="4.5" fill="#F59E0B" stroke="#FFFFFF" stroke-width="2"/>'
    "</svg>"
)

FILTER_LABELS = {
    "{{ Dimension('contributor__is_bot') }} = false": "Excludes bots",
    "{{ Dimension('contributor__is_bot') }} = true": "Bots only",
}


# --- Charts (same look as the Streamlit app) ---------------------------------------------
def style(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=GRID,
            domain=False,
            tickColor=GRID,
            labelColor=MUTED,
            titleColor=MUTED,
            labelFontSize=12,
            titleFontSize=12,
        )
        .configure_legend(orient="top", title=None, labelColor=INK, labelFontSize=12)
    )


def stacked_chart(weekly) -> dict:
    data = humans_vs_bots(weekly[["week", "week_label", "contributions", "bot_contributions"]])
    chart = (
        alt.Chart(data[["week_label", "who", "count"]])
        .mark_area(opacity=0.9, interpolate="monotone")
        .encode(
            x=alt.X("week_label:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title="Contributions", stack="zero"),
            color=alt.Color(
                "who:N", scale=alt.Scale(domain=["Humans", "Bots"], range=[HUMAN, BOT])
            ),
            order=alt.Order("who:N", sort="descending"),
            tooltip=[
                alt.Tooltip("week_label:N", title="Week of"),
                "who:N",
                alt.Tooltip("count:Q", format=","),
            ],
        )
        .properties(width="container", height=320)
    )
    return style(chart).to_dict()


def contributors_chart(weekly) -> dict:
    chart = (
        alt.Chart(weekly[["week_label", "active_contributors"]])
        .mark_line(color=HUMAN, strokeWidth=3, point=alt.OverlayMarkDef(size=60))
        .encode(
            x=alt.X("week_label:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("active_contributors:Q", title="Contributors", scale=alt.Scale(zero=True)),
            tooltip=[
                alt.Tooltip("week_label:N", title="Week of"),
                alt.Tooltip("active_contributors:Q", format=","),
            ],
        )
        .properties(width="container", height=320)
    )
    return style(chart).to_dict()


def bar_chart(df, column: str, title: str, color: str, ascending: bool) -> dict:
    chart = (
        alt.Chart(df[["repository", column]].dropna())
        .mark_bar(color=color, cornerRadiusEnd=4)
        .encode(
            x=alt.X(f"{column}:Q", title=title),
            y=alt.Y("repository:N", title=None, sort="x" if ascending else "-x"),
            tooltip=["repository", alt.Tooltip(f"{column}:Q", format=",.1f")],
        )
        .properties(width="container", height=400)
    )
    return style(chart).to_dict()


# --- HTML helpers ----------------------------------------------------------------------
def kpi(label: str, value: str, note: str) -> str:
    return (
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="note">{note}</div></div>'
    )


def fmt_hours(value) -> str:
    return "–" if value is None or value != value else f"{value:.1f}"  # NaN-safe


def fmt_pct(value) -> str:
    return "–" if value is None or value != value else f"{value:.0%}"


def repo_table(df) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(r.repository))}</td>"
        f'<td class="num">{int(r.prs_merged):,}</td>'
        f'<td class="num">{fmt_pct(r.pr_merge_rate)}</td>'
        f'<td class="num">{fmt_hours(r.median_hours_to_merge)}</td>'
        f'<td class="num">{fmt_hours(r.median_hours_to_first_response)}</td>'
        "</tr>"
        for r in df.itertuples()
    )
    return (
        '<table><thead><tr><th>Repository</th><th class="num">PRs merged</th>'
        '<th class="num">Merge rate</th><th class="num">Median hours to merge</th>'
        '<th class="num">Median hours to first reply</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def catalog_table(df) -> str:
    rows = "".join(
        "<tr>"
        f"<td><strong>{html.escape(str(r.label))}</strong><br>"
        f'<span class="code">{html.escape(str(r.metric))}</span></td>'
        f"<td>{html.escape(str(r.type))}</td>"
        f"<td>{html.escape(str(r.definition))}</td>"
        f"<td>{html.escape(FILTER_LABELS.get(r.filter, r.filter) or '–')}</td>"
        "</tr>"
        for r in df.itertuples()
    )
    return (
        "<table><thead><tr><th>Metric</th><th>Type</th><th>Definition</th>"
        f"<th>Filter</th></tr></thead><tbody>{rows}</tbody></table>"
    )


# --- Build -----------------------------------------------------------------------------
def build() -> Path:
    today = dt.date.today()
    window = {"start_time": DATA_START.isoformat(), "end_time": today.isoformat()}

    totals = query_metrics(
        [
            "active_contributors",
            "contributions",
            "bot_contributions",
            "bot_contribution_share",
            "prs_merged",
        ],
        **window,
    ).iloc[0]

    weekly = complete_weeks(
        query_metrics(
            ["contributions", "bot_contributions", "active_contributors"],
            group_by=["metric_time__week"],
            order=["metric_time__week"],
            **window,
        ),
        DATA_START,
        today,
    )
    weekly["week_label"] = weekly["week"].dt.strftime("%b %d")

    by_repo = query_metrics(
        ["prs_merged", "pr_merge_rate", "median_hours_to_merge", "median_hours_to_first_response"],
        group_by=["repo__repo_name"],
        order=["-prs_merged"],
        limit=12,
        **window,
    ).rename(columns={"repo__repo_name": "repository"})

    specs = {
        "stacked": stacked_chart(weekly),
        "contributors": contributors_chart(weekly),
        "merged": bar_chart(by_repo, "prs_merged", "PRs merged", HUMAN, ascending=False),
        "reply": bar_chart(
            by_repo,
            "median_hours_to_first_response",
            "Hours (lower is faster)",
            TEAL,
            ascending=True,
        ),
    }

    share = float(totals.bot_contribution_share)
    page = TEMPLATE.format(
        title=TITLE,
        subtitle=SUBTITLE,
        logo=LOGO_SVG,
        period=f"{DATA_START:%b %d} – {today:%b %d, %Y}",
        updated=f"{today:%b %d, %Y}",
        share_pct=f"{share:.0%}",
        bots=f"{int(totals.bot_contributions):,}",
        humans=f"{int(totals.contributions):,}",
        kpis="".join(
            [
                kpi(
                    "Active contributors", f"{int(totals.active_contributors):,}", "distinct humans"
                ),
                kpi(
                    "Human contributions", f"{int(totals.contributions):,}", "PRs, issues, comments"
                ),
                kpi("PRs merged", f"{int(totals.prs_merged):,}", "authored by humans"),
                kpi("Bot share", f"{share:.1%}", "of all contributions"),
            ]
        ),
        repo_table=repo_table(by_repo),
        catalog_table=catalog_table(metric_catalog()),
        repo_url=REPO_URL,
        specs=json.dumps(specs),
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    (OUTPUT.parent / ".nojekyll").touch()  # serve files as-is on GitHub Pages
    return OUTPUT


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{subtitle}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap"
      rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<style>
  :root {{ --ink:#0F172A; --muted:#64748B; --line:#E2E8F0; --bg:#F8FAFC; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family: Inter, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 36px 24px 48px; }}
  .brand {{ display:flex; align-items:center; gap:16px; }}
  .brand h1 {{ font-size: clamp(1.6rem, 3.2vw, 2.4rem); font-weight:800; margin:0;
              letter-spacing:-0.02em; line-height:1.1; }}
  .subtitle {{ color:#475569; font-size:1.05rem; margin:10px 0 14px; }}
  .badges span {{ display:inline-block; background:#EEF2F7; color:#334155; border-radius:999px;
                 padding:4px 12px; font-size:.8rem; font-weight:600; margin:0 6px 6px 0; }}
  .hero {{ background:linear-gradient(135deg,#EFF6FF 0%,#FFF7ED 100%); border:1px solid var(--line);
          border-radius:18px; padding:24px 28px; margin:18px 0 22px; }}
  .hero .big {{ font-size: clamp(1.25rem, 2.6vw, 1.75rem); font-weight:800; line-height:1.25; }}
  .hero .big .bot {{ color:#D97706; }}
  .hero .small {{ color:#475569; margin-top:6px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
  .kpi {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px 20px;
         box-shadow:0 1px 2px rgba(15,23,42,.05); }}
  .kpi .label {{ color:var(--muted); font-size:.75rem; font-weight:700; text-transform:uppercase;
                letter-spacing:.05em; }}
  .kpi .value {{ font-size:2rem; font-weight:800; margin-top:4px; }}
  .kpi .note {{ color:var(--muted); font-size:.8rem; }}
  .row {{ display:grid; grid-template-columns:3fr 2fr; gap:28px; margin-top:28px; }}
  .row.even {{ grid-template-columns:1fr 1fr; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px 20px; }}
  h2 {{ font-size:1.15rem; margin:0; }}
  .note {{ color:var(--muted); font-size:.88rem; margin:2px 0 8px; }}
  .chart {{ width:100%; }}
  h3.section {{ font-size:1.35rem; margin:40px 0 4px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.92rem; background:#fff; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line);
            vertical-align:top; }}
  th {{ color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }}
  td.num, th.num {{ text-align:right; }}
  .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:14px; }}
  .code {{ font-family: ui-monospace, Menlo, monospace; color:var(--muted); font-size:.8rem; }}
  footer {{ color:var(--muted); font-size:.85rem; text-align:center; margin-top:40px; }}
  footer a {{ color:#2563EB; text-decoration:none; }}
  @media (max-width: 900px) {{
    .kpis {{ grid-template-columns:repeat(2,1fr); }}
    .row, .row.even {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">{logo}<h1>{title}</h1></div>
  <div class="subtitle">{subtitle}</div>
  <div class="badges">
    <span>64 repositories</span><span>{period}</span>
    <span>Governed metrics · dbt + MetricFlow</span><span>Airflow · Snowflake</span>
    <span>Last updated {updated}</span>
  </div>

  <div class="hero">
    <div class="big"><span class="bot">{share_pct}</span> of all activity in these
      communities comes from bots.</div>
    <div class="small">{bots} bot contributions vs {humans} human contributions.
      Every human metric on this page excludes bots by definition.</div>
  </div>

  <div class="kpis">{kpis}</div>

  <div class="row">
    <div class="card"><h2>Weekly contributions: humans vs bots</h2>
      <div class="note">Stacked: the amber band is automation. Complete weeks only.</div>
      <div id="stacked" class="chart"></div></div>
    <div class="card"><h2>Active contributors per week</h2>
      <div class="note">Distinct humans with at least one contribution.</div>
      <div id="contributors" class="chart"></div></div>
  </div>

  <h3 class="section">Projects</h3>
  <div class="row even">
    <div class="card"><h2>Most active projects</h2>
      <div class="note">Human pull requests merged.</div>
      <div id="merged" class="chart"></div></div>
    <div class="card"><h2>How fast do they reply?</h2>
      <div class="note">Median hours to the first human reply on a PR.</div>
      <div id="reply" class="chart"></div></div>
  </div>
  <div class="table-wrap" style="margin-top:20px">{repo_table}</div>
  <div class="note" style="margin-top:8px">Merge rate uses the PR's open date, so recent PRs may
    not be merged yet. Some Apache projects merge outside GitHub's merge button.</div>

  <h3 class="section">Metric definitions</h3>
  <div class="note">Every number above is defined once, in dbt's semantic layer.</div>
  <div class="table-wrap">{catalog_table}</div>

  <footer>Built with Airflow · Snowflake · dbt · MetricFlow &nbsp;|&nbsp;
    <a href="{repo_url}">Source code on GitHub</a></footer>
</div>
<script>
  const specs = {specs};
  for (const [id, spec] of Object.entries(specs)) {{
    vegaEmbed("#" + id, spec, {{ actions: false, renderer: "svg" }});
  }}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(f"Wrote {build()}")
