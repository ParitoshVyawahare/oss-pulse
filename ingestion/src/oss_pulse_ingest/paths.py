"""Landing-zone layout. Kept separate from landing.py so it has no heavy imports."""

from datetime import datetime
from pathlib import Path


def partition_dir(landing_dir: Path, hour: datetime) -> Path:
    """Hive-style partitions: gh_events/event_date=2026-09-21/event_hour=15/

    Snowflake, DuckDB, Spark and pyarrow all understand this layout, and it maps
    one Airflow task (one hour) to exactly one folder.
    """
    return landing_dir / "gh_events" / f"event_date={hour:%Y-%m-%d}" / f"event_hour={hour.hour:02d}"


def manifest_path(landing_dir: Path, hour: datetime) -> Path:
    return partition_dir(landing_dir, hour) / "_manifest.json"
