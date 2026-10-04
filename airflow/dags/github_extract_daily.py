"""
### GitHub extraction (daily)

Runs once a day at 00:00 UTC. Airflow 3 gives cron schedules a zero-width data
interval, so each run extracts **the previous full UTC day** (see
`Window.from_interval`). Output: raw-JSON Parquet in `data/landing/github/`.
Reruns overwrite the same files, so retries are safe.
"""

from __future__ import annotations

from airflow.sdk import dag
from oss_pulse_dags.github_extraction import DEFAULT_ARGS, github_extraction
from pendulum import datetime


@dag(
    dag_id="github_extract_daily",
    start_date=datetime(2026, 10, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,  # never let two runs hit the API at the same time
    default_args=DEFAULT_ARGS,
    tags=["oss-pulse", "ingestion"],
    doc_md=__doc__,
)
def github_extract_daily():
    github_extraction()


github_extract_daily()
