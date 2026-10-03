"""Paths and settings. Every value can be overridden with an environment variable,
which is how Airflow will configure this package in week 2."""

import os
from pathlib import Path

# config.py -> oss_pulse_ingest -> src -> ingestion -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

LANDING_DIR = Path(os.getenv("LANDING_DIR", REPO_ROOT / "data" / "landing"))
CATALOG_PATH = Path(
    os.getenv("REPO_CATALOG_PATH", REPO_ROOT / "dbt" / "seeds" / "repo_catalog.csv")
)
