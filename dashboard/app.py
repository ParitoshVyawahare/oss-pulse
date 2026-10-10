"""GitHub Community Health Analytics dashboard. Run from the repo root:

    uv run --env-file .env streamlit run dashboard/app.py

Every number comes from a governed MetricFlow metric (see metrics_client.py):
there is deliberately no SQL in this file.
"""

from __future__ import annotations

import base64
import datetime as dt

import altair as alt
import streamlit as st
from metrics_client import MetricQueryError, metric_catalog, query_metrics
from transforms import complete_weeks, humans_vs_bots

TITLE = "GitHub Community Health Analytics"
SUBTITLE = (
    "How active are the communities behind 64 popular open-source data tools, "
    "and how much of the work is done by bots?"
)
REPO_URL = "https://github.com/ParitoshVyawahare/oss-pulse"
DATA_START = dt.date(2026, 8, 1)

HUMAN = "#2563EB"  # blue
BOT = "#F59E0B"  # amber
TEAL = "#0EA5E9"
INK = "#0F172A"
MUTED = "#64748B"
GRID = "#EEF2F7"

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 52 52">'
    '<rect width="52" height="52" rx="14" fill="#2563EB"/>'
    '<polyline points="11,34 20,24 28,30 40,16" fill="none" stroke="#FFFFFF" '
    'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="40" cy="16" r="4.5" fill="#F59E0B" stroke="#FFFFFF" stroke-width="2"/>'
    "</svg>"
)

st.set_page_config(
    page_title=TITLE, page_icon="📊", layout="wide", initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
      #MainMenu, footer {visibility: hidden;}
      [data-testid="stHeader"] {background: transparent;}
      .block-container {padding-top: 2.2rem; max-width: 1240px;}
      h1 {font-weight: 800 !important; letter-spacing: -0.02em; margin-bottom: 0 !important;}
      .brand {display: flex; align-items: center; gap: 16px;}
      .brand img {width: 52px; height: 52px;}
      .brand-title {font-size: 2.4rem; font-weight: 800; color: #0F172A;
                    letter-spacing: -0.02em; line-height: 1.1; margin: 0;}
      .subtitle {color: #475569; font-size: 1.05rem; margin: 0.35rem 0 0.8rem;}
      .badges span {display: inline-block; background: #EEF2F7; color: #334155;
                    border-radius: 999px; padding: 4px 12px; font-size: 0.8rem;
                    font-weight: 600; margin: 0 6px 6px 0;}
      .hero {background: linear-gradient(135deg, #EFF6FF 0%, #FFF7ED 100%);
             border: 1px solid #E2E8F0; border-radius: 18px; padding: 24px 28px;
             margin: 14px 0 22px;}
      .hero .big {font-size: 1.75rem; font-weight: 800; color: #0F172A; line-height: 1.25;}
      .hero .big .bot {color: #D97706;}
      .hero .small {color: #475569; margin-top: 6px; font-size: 0.95rem;}
      .kpi {background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
            padding: 18px 20px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); height: 100%;}
      .kpi .label {color: #64748B; font-size: 0.78rem; font-weight: 700;
                   text-transform: uppercase; letter-spacing: 0.05em;}
      .kpi .value {color: #0F172A; font-size: 2rem; font-weight: 800; margin-top: 4px;}
      .kpi .note {color: #64748B; font-size: 0.8rem; margin-top: 2px;}
      .section {font-size: 1.15rem; font-weight: 750; color: #0F172A; margin: 18px 0 2px;}
      .section-note {color: #64748B; font-size: 0.88rem; margin-bottom: 6px;}
      .footer {color: #64748B; font-size: 0.85rem; text-align: center; margin-top: 36px;}
      .footer a {color: #2563EB; text-decoration: none;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner="Querying governed metrics...")
def metrics(names: tuple[str, ...], **kwargs):
    """Cached wrapper: the same question within an hour is answered instantly."""
    return query_metrics(list(names), **kwargs)


def kpi(label: str, value: str, note: str = "") -> str:
    return (
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="note">{note}</div></div>'
    )


def section(title: str, note: str = "") -> None:
    st.markdown(
        f'<div class="section">{title}</div><div class="section-note">{note}</div>',
        unsafe_allow_html=True,
    )


def style(chart: alt.Chart) -> alt.Chart:
    """One consistent, minimal chart style for the whole dashboard."""
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


# --- Filters (sidebar, collapsed by default for clean screenshots) -----------------
with st.sidebar:
    st.header("Filters")
    start = st.date_input("From", DATA_START, min_value=DATA_START)
    end = st.date_input("To", dt.date.today(), min_value=DATA_START)
    st.caption("Charts show complete weeks only. Data collection began on 2026-08-01.")

window = {"start_time": start.isoformat(), "end_time": end.isoformat()}

# --- Header -------------------------------------------------------------------------
logo_b64 = base64.b64encode(LOGO_SVG.encode()).decode()
st.markdown(
    f'<div class="brand"><img src="data:image/svg+xml;base64,{logo_b64}" alt="logo">'
    f'<div class="brand-title">{TITLE}</div></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="subtitle">{SUBTITLE}</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="badges"><span>64 repositories</span>'
    f"<span>{start:%b %d} – {end:%b %d, %Y}</span>"
    "<span>Governed metrics · dbt + MetricFlow</span>"
    "<span>Airflow · Snowflake</span></div>",
    unsafe_allow_html=True,
)

overview_tab, projects_tab, definitions_tab = st.tabs(
    ["Overview", "Projects", "Metric definitions"]
)

try:
    # --- Overview ---------------------------------------------------------------------
    with overview_tab:
        totals = metrics(
            (
                "active_contributors",
                "contributions",
                "bot_contributions",
                "bot_contribution_share",
                "prs_merged",
            ),
            **window,
        ).iloc[0]

        st.markdown(
            '<div class="hero"><div class="big">'
            f'<span class="bot">{totals.bot_contribution_share:.0%}</span> of all activity '
            "in these communities comes from bots.</div>"
            f'<div class="small">{int(totals.bot_contributions):,} bot contributions vs '
            f"{int(totals.contributions):,} human contributions. Every human metric on this "
            "page excludes bots by definition.</div></div>",
            unsafe_allow_html=True,
        )

        cols = st.columns(4)
        cols[0].markdown(
            kpi("Active contributors", f"{int(totals.active_contributors):,}", "distinct humans"),
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            kpi("Human contributions", f"{int(totals.contributions):,}", "PRs, issues, comments"),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            kpi("PRs merged", f"{int(totals.prs_merged):,}", "authored by humans"),
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            kpi("Bot share", f"{totals.bot_contribution_share:.1%}", "of all contributions"),
            unsafe_allow_html=True,
        )

        weekly = complete_weeks(
            metrics(
                ("contributions", "bot_contributions", "active_contributors"),
                group_by=("metric_time__week",),
                order=("metric_time__week",),
                **window,
            ),
            start,
            end,
        )

        weekly["week_label"] = weekly["week"].dt.strftime("%b %d")
        left, right = st.columns([3, 2], gap="large")
        with left:
            section(
                "Weekly contributions: humans vs bots",
                "Stacked: the amber band is automation.",
            )
            stacked = (
                alt.Chart(humans_vs_bots(weekly))
                .mark_area(opacity=0.9, interpolate="monotone")
                .encode(
                    x=alt.X("week_label:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("count:Q", title="Contributions", stack="zero"),
                    color=alt.Color(
                        "who:N",
                        scale=alt.Scale(domain=["Humans", "Bots"], range=[HUMAN, BOT]),
                    ),
                    order=alt.Order("who:N", sort="descending"),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week of"),
                        "who:N",
                        alt.Tooltip("count:Q", format=","),
                    ],
                )
                .properties(height=330)
            )
            st.altair_chart(style(stacked), width="stretch")
        with right:
            section(
                "Active contributors per week",
                "Distinct humans with at least one contribution.",
            )
            line = (
                alt.Chart(weekly)
                .mark_line(color=HUMAN, strokeWidth=3, point=alt.OverlayMarkDef(size=60))
                .encode(
                    x=alt.X("week_label:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "active_contributors:Q",
                        title="Contributors",
                        scale=alt.Scale(zero=True),
                    ),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week of"),
                        alt.Tooltip("active_contributors:Q", format=","),
                    ],
                )
                .properties(height=330)
            )
            st.altair_chart(style(line), width="stretch")

    # --- Projects -----------------------------------------------------------------------
    with projects_tab:
        by_repo = metrics(
            (
                "prs_merged",
                "pr_merge_rate",
                "median_hours_to_merge",
                "median_hours_to_first_response",
            ),
            group_by=("repo__repo_name",),
            order=("-prs_merged",),
            limit=12,
            **window,
        ).rename(columns={"repo__repo_name": "repository"})

        left, right = st.columns(2, gap="large")
        with left:
            section("Most active projects", "Human pull requests merged.")
            bars = (
                alt.Chart(by_repo)
                .mark_bar(color=HUMAN, cornerRadiusEnd=4)
                .encode(
                    x=alt.X("prs_merged:Q", title="PRs merged"),
                    y=alt.Y("repository:N", title=None, sort="-x"),
                    tooltip=["repository", alt.Tooltip("prs_merged:Q", format=",")],
                )
                .properties(height=420)
            )
            st.altair_chart(style(bars), width="stretch")
        with right:
            section("How fast do they reply?", "Median hours to the first human reply on a PR.")
            reply = (
                alt.Chart(by_repo.dropna(subset=["median_hours_to_first_response"]))
                .mark_bar(color=TEAL, cornerRadiusEnd=4)
                .encode(
                    x=alt.X("median_hours_to_first_response:Q", title="Hours (lower is faster)"),
                    y=alt.Y("repository:N", title=None, sort="x"),
                    tooltip=[
                        "repository",
                        alt.Tooltip("median_hours_to_first_response:Q", format=".1f"),
                    ],
                )
                .properties(height=420)
            )
            st.altair_chart(style(reply), width="stretch")

        section("Details")
        st.dataframe(
            by_repo,
            hide_index=True,
            width="stretch",
            column_config={
                "repository": "Repository",
                "prs_merged": st.column_config.NumberColumn("PRs merged", format="%d"),
                "pr_merge_rate": st.column_config.ProgressColumn(
                    "Merge rate", format="percent", min_value=0, max_value=1
                ),
                "median_hours_to_merge": st.column_config.NumberColumn(
                    "Median hours to merge", format="%.1f"
                ),
                "median_hours_to_first_response": st.column_config.NumberColumn(
                    "Median hours to first reply", format="%.1f"
                ),
            },
        )
        st.caption(
            "Merge rate uses the PR's open date, so recent PRs may not be merged yet. "
            "Some Apache projects merge outside GitHub's merge button, so they show few merges."
        )

    # --- Metric definitions ----------------------------------------------------------------
    with definitions_tab:
        section(
            "Governed metric definitions",
            "Each number on this dashboard is defined once, in dbt. Change a definition there, "
            "and every chart, query and report updates together.",
        )
        st.dataframe(metric_catalog(), hide_index=True, width="stretch")

except MetricQueryError as err:
    st.error("A metric query failed. Details:")
    st.code(str(err))

st.markdown(
    '<div class="footer">Built with Airflow · Snowflake · dbt · MetricFlow · Streamlit'
    f' &nbsp;|&nbsp; <a href="{REPO_URL}" target="_blank">Source code on GitHub</a></div>',
    unsafe_allow_html=True,
)
