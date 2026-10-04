"""
### GitHub extraction (monthly backfill)

Loads **history**, one calendar month per run. Unlike the daily DAG, this one uses
`CronDataIntervalTimetable`, so every run gets a **real** data interval:
the run for March 2026 covers `2026-03-01 -> 2026-04-01`.

Why monthly instead of daily? Every run costs a fixed ~320 API requests just to
visit 64 repos x 5 resources, so 6 monthly runs are far cheaper than ~180 daily runs.

Start it with an Airflow backfill (UI: Trigger -> Backfill), never by catchup.
`end_date` stops it from ever scheduling new runs: ongoing data is the daily DAG's job.
"""

from __future__ import annotations

from airflow.sdk import dag
from airflow.timetables.interval import CronDataIntervalTimetable
from oss_pulse_dags.github_extraction import DEFAULT_ARGS, github_extraction
from pendulum import UTC, datetime


@dag(
    dag_id="github_extract_backfill_monthly",
    start_date=datetime(2025, 10, 1, tz="UTC"),
    end_date=datetime(2026, 8, 31, tz="UTC"),  # history only; September onward is covered
    schedule=CronDataIntervalTimetable("0 0 1 * *", timezone=UTC),  # 1st of each month
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["oss-pulse", "ingestion", "backfill"],
    doc_md=__doc__,
)
def github_extract_backfill_monthly():
    github_extraction()


github_extract_backfill_monthly()
