"""The GitHub extraction steps, shared by the daily DAG and the monthly backfill DAG.

Both DAGs run the exact same tasks; only their schedules differ. Keeping the tasks
here means a fix (or a new resource) lands in both DAGs at once.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.sdk import Asset, task

from oss_pulse_dags.alerts import notify_slack_on_failure

# Downstream DAGs (dbt, week 3+) will be scheduled on this Asset instead of a clock time.
GITHUB_LANDING = Asset("oss_pulse_github_landing")

DEFAULT_ARGS = {
    "owner": "paritosh",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "on_failure_callback": notify_slack_on_failure,  # Slack message after the final retry
}

RESULT_KEYS = ("repos", "pulls", "issues", "comments", "releases", "requests")


def github_extraction():
    """Add list_repos -> extract_repo (mapped) -> summarize to the current DAG."""

    @task
    def list_repos() -> list[dict]:
        # Imports live INSIDE tasks: the DAG processor re-reads DAG files often,
        # so top-level code must stay fast and must not depend on project code.
        from oss_pulse_ingest.catalog import load_catalog_rows
        from oss_pulse_ingest.config import CATALOG_PATH

        rows = load_catalog_rows(CATALOG_PATH)
        return [{"repo_id": int(r["repo_id"]), "repo_name": r["repo_name"]} for r in rows]

    @task(max_active_tis_per_dagrun=4)  # at most 4 repos at once: gentle on GitHub
    def extract_repo(repo: dict, **context) -> dict:
        from oss_pulse_ingest.config import LANDING_DIR
        from oss_pulse_ingest.extract import RESOURCES, Window, extract
        from oss_pulse_ingest.github_api import GitHubClient

        # Real interval (monthly backfill) -> used as-is.
        # Zero-width interval (Airflow 3 cron default, manual runs) -> previous full UTC day.
        window = Window.from_interval(
            context.get("data_interval_start"), context.get("data_interval_end")
        )
        client = GitHubClient()
        counts = {
            resource: extract(
                client,
                resource=resource,
                repo_id=repo["repo_id"],
                repo_name=repo["repo_name"],
                window=window,
                landing_dir=LANDING_DIR,
            )
            for resource in RESOURCES
        }
        print(f"{repo['repo_name']} window={window.label} {counts} requests={client.request_count}")
        return {"window": window.label, **counts, "requests": client.request_count}

    @task(outlets=[GITHUB_LANDING])
    def summarize(results: list[dict]) -> dict:
        results = list(results)
        totals = {key: sum(r[key] for r in results) for key in RESULT_KEYS}
        print(f"Window {results[0]['window']}: {len(results)} repos extracted, totals={totals}")
        return totals

    return summarize(extract_repo.expand(repo=list_repos()))
