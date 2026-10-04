"""Slack alerting for OSS Pulse DAGs.

`notify_slack_on_failure` is an Airflow *failure callback*: Airflow calls it once a
task has failed for good (after its last retry), not on every intermediate retry.
"""

from __future__ import annotations

import os


def notify_slack_on_failure(context) -> None:
    """Post a short failure summary to the Slack channel behind SLACK_WEBHOOK_URL."""
    import requests  # imported here so DAG parsing stays fast

    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        print("SLACK_WEBHOOK_URL is not set; skipping Slack alert")
        return

    ti = context["ti"]
    dag_run = context.get("dag_run")
    map_index = getattr(ti, "map_index", -1)
    task = ti.task_id if map_index is None or map_index < 0 else f"{ti.task_id}[{map_index}]"
    error = str(context.get("exception") or "unknown error")[:300]

    text = (
        ":red_circle: *Airflow task failed*\n"
        f"*DAG:* `{ti.dag_id}`\n"
        f"*Task:* `{task}`\n"
        f"*Run:* `{dag_run.run_id if dag_run else 'unknown'}`\n"
        f"*Attempts:* {ti.try_number}\n"
        f"*Error:* {error}"
    )
    try:
        requests.post(url, json={"text": text}, timeout=10).raise_for_status()
    except Exception as exc:  # an alerting problem must never hide the original failure
        print(f"Could not send Slack alert: {exc}")
