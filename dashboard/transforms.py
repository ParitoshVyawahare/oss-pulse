"""Small, pure data-shaping helpers for the dashboard (pandas only, easy to test)."""

from __future__ import annotations

import datetime as dt

import pandas as pd


def complete_weeks(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Keep only weeks that lie fully inside [start, end].

    Partial weeks (the week containing the first day of data, or the current week)
    look like sudden drops on a chart even though nothing changed. Dropping them keeps
    charts honest.
    """
    week_start = pd.to_datetime(df["metric_time__week"]).dt.date
    keep = (week_start >= start) & (week_start + dt.timedelta(days=6) <= end)
    out = df.loc[keep].copy()
    out["week"] = pd.to_datetime(week_start[keep])
    return out.sort_values("week").reset_index(drop=True)


def humans_vs_bots(weekly: pd.DataFrame) -> pd.DataFrame:
    """Reshape weekly human and bot contributions into long format for a stacked chart."""
    long = weekly.melt(
        id_vars=[c for c in ("week", "week_label") if c in weekly.columns],
        value_vars=["contributions", "bot_contributions"],
        var_name="who",
        value_name="count",
    )
    long["who"] = long["who"].map({"contributions": "Humans", "bot_contributions": "Bots"})
    return long
