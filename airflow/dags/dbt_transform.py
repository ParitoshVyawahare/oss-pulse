"""
### dbt transform (data-aware)

Runs whenever new GitHub data lands in Snowflake BRONZE (the `oss_pulse_github_bronze`
Asset), not on a clock. Astronomer Cosmos turns every dbt model and seed into its own
Airflow task, each followed by its tests, so failures can be seen, retried and alerted
on individually.
"""

from __future__ import annotations

from pathlib import Path

from cosmos import DbtDag, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import TestBehavior
from oss_pulse_dags.github_extraction import DEFAULT_ARGS, GITHUB_BRONZE
from pendulum import datetime

DBT_PROJECT = Path("/usr/local/airflow/oss-pulse/dbt")
DBT_EXECUTABLE = Path("/usr/local/airflow/dbt_venv/bin/dbt")

# The dbt project is mounted into local Airflow only (docker-compose.override.yml).
# In environments without it (e.g. the DAG integrity tests), skip creating the DAG.
if DBT_PROJECT.exists():
    dbt_transform = DbtDag(
        dag_id="dbt_transform",
        project_config=ProjectConfig(DBT_PROJECT),
        profile_config=ProfileConfig(
            profile_name="oss_pulse",
            target_name="dev",
            profiles_yml_filepath=DBT_PROJECT / "profiles.yml",
        ),
        execution_config=ExecutionConfig(dbt_executable_path=str(DBT_EXECUTABLE)),
        render_config=RenderConfig(test_behavior=TestBehavior.AFTER_EACH),
        schedule=[GITHUB_BRONZE],  # data-aware: run when BRONZE gets new rows
        start_date=datetime(2026, 10, 1, tz="UTC"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,  # retries + Slack alert on final failure
        tags=["oss-pulse", "dbt"],
        doc_md=__doc__,
    )
