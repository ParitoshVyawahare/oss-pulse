"""
### Publish the public dashboard (data-aware)

Runs when dbt has rebuilt the gold fact tables: Cosmos emits one Asset per dbt model,
and this DAG is scheduled on two of them. It rebuilds the static dashboard from the
governed MetricFlow metrics and publishes docs/index.html to GitHub Pages through the
GitHub API (the local working copy is never touched).
"""

from __future__ import annotations

import os

from airflow.sdk import Asset, dag, task
from oss_pulse_dags.github_extraction import DEFAULT_ARGS
from pendulum import datetime

REPO_DIR = "/usr/local/airflow/oss-pulse"
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "KVSICWP-JT26707")

# Asset URIs exactly as Cosmos emits them for these dbt models.
GOLD_FACTS = [
    Asset(f"snowflake://{SNOWFLAKE_ACCOUNT}/OSS_PULSE_DEV/gold/{table}")
    for table in ("fct_contributions", "fct_pull_requests")
]


@dag(
    dag_id="publish_dashboard",
    schedule=GOLD_FACTS,  # runs once BOTH fact tables have been rebuilt
    start_date=datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["oss-pulse", "dashboard"],
    doc_md=__doc__,
)
def publish_dashboard():
    @task
    def build_page() -> str:
        """Run the governed metrics and render the static page into /tmp."""
        import sys
        from pathlib import Path

        sys.path.insert(0, f"{REPO_DIR}/dashboard")
        from build_static import build

        return str(build(output=Path("/tmp/oss_pulse_site/index.html")))

    @task
    def publish(page_path: str) -> str:
        """Commit the page to docs/index.html on main via the GitHub Contents API."""
        import sys
        from pathlib import Path

        sys.path.insert(0, f"{REPO_DIR}/dashboard")
        from publish_github import publish_file

        result = publish_file(
            Path(page_path),
            repo="ParitoshVyawahare/oss-pulse",
            path_in_repo="docs/index.html",
            token=os.environ["GITHUB_PUBLISH_TOKEN"],
        )
        print(f"docs/index.html: {result}")
        return result

    publish(build_page())


publish_dashboard()
