"""
### Alerting smoke test

Fails **on purpose** so you can confirm Slack alerts work end to end.
Trigger it manually after changing alerting config. It retries twice (5 seconds
apart) and then sends exactly **one** Slack message: the callback fires only after
the final retry, not on every attempt.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.sdk import dag, task
from oss_pulse_dags.alerts import notify_slack_on_failure
from pendulum import datetime


@dag(
    dag_id="alerting_smoke_test",
    start_date=datetime(2026, 10, 1, tz="UTC"),
    schedule=None,  # manual only
    catchup=False,
    default_args={
        "owner": "paritosh",
        "retries": 2,
        "retry_delay": timedelta(seconds=5),
        "on_failure_callback": notify_slack_on_failure,
    },
    tags=["oss-pulse", "ops"],
    doc_md=__doc__,
)
def alerting_smoke_test():
    @task
    def fail_on_purpose() -> None:
        raise RuntimeError("Intentional failure to test Slack alerting. Nothing is broken.")

    fail_on_purpose()


alerting_smoke_test()
