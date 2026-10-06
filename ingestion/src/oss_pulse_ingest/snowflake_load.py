"""Load landed Parquet files into Snowflake BRONZE.

Steps for each landing folder (one resource + one window, e.g. pulls/window=...):
  1. PUT    upload the folder's Parquet files to an internal Snowflake stage
  2. DELETE remove any rows previously loaded from that same folder
  3. COPY   load the files into BRONZE.GITHUB_RAW (FORCE, so re-uploads load again)
Steps 2 and 3 run in ONE transaction, so a rerun replaces a folder's rows instead of
duplicating them, and nobody ever sees a half-loaded folder. That makes loads idempotent,
just like the extraction.

All five resources go into one table; `record` is a VARIANT (Snowflake's JSON type).
dbt staging models split it by `resource` and parse the JSON (ELT).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

STAGE = "bronze.github_landing"
TABLE = "bronze.github_raw"
FILE_FORMAT = "bronze.parquet_format"

SETUP_SQL = [
    f"""CREATE FILE FORMAT IF NOT EXISTS {FILE_FORMAT}
          TYPE = PARQUET USE_VECTORIZED_SCANNER = TRUE""",
    f"CREATE STAGE IF NOT EXISTS {STAGE} FILE_FORMAT = {FILE_FORMAT}",
    f"""CREATE TABLE IF NOT EXISTS {TABLE} (
          resource           STRING        NOT NULL,
          repo_id            NUMBER        NOT NULL,
          repo_name          STRING,
          record_id          STRING        NOT NULL,
          record_updated_at  TIMESTAMP_TZ,
          record             VARIANT,
          _window_start      TIMESTAMP_TZ,
          _window_end        TIMESTAMP_TZ,
          _extracted_at      TIMESTAMP_TZ,
          _source_file       STRING,
          _loaded_at         TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP()
        )""",
]


@dataclass(frozen=True)
class Partition:
    """One landing folder, e.g. resource='pulls', folder='window=2026-09-01_2026-10-01'."""

    resource: str
    folder: str
    local_dir: Path

    @property
    def stage_prefix(self) -> str:
        return f"{self.resource}/{self.folder}/"


def find_partitions(landing_dir: Path, resources: list[str] | None = None) -> list[Partition]:
    """Every landing folder that contains at least one Parquet file."""
    root = landing_dir / "github"
    found = []
    for resource_dir in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        if resources and resource_dir.name not in resources:
            continue
        for folder in sorted(p for p in resource_dir.iterdir() if p.is_dir()):
            if any(folder.glob("*.parquet")):
                found.append(Partition(resource_dir.name, folder.name, folder))
    return found


def put_sql(p: Partition) -> str:
    return (
        f"PUT 'file://{p.local_dir.resolve()}/*.parquet' '@{STAGE}/{p.stage_prefix}' "
        "AUTO_COMPRESS = FALSE OVERWRITE = TRUE"
    )


def delete_sql(p: Partition) -> str:
    return f"DELETE FROM {TABLE} WHERE _source_file LIKE '{p.stage_prefix}%'"


def copy_sql(p: Partition) -> str:
    return f"""
COPY INTO {TABLE} (resource, repo_id, repo_name, record_id, record_updated_at, record,
                   _window_start, _window_end, _extracted_at, _source_file)
FROM (
  SELECT $1:resource::STRING, $1:repo_id::NUMBER, $1:repo_name::STRING, $1:record_id::STRING,
         $1:record_updated_at::TIMESTAMP_TZ, PARSE_JSON($1:record::STRING),
         $1:_window_start::TIMESTAMP_TZ, $1:_window_end::TIMESTAMP_TZ,
         $1:_extracted_at::TIMESTAMP_TZ, METADATA$FILENAME
  FROM @{STAGE}/{p.stage_prefix}
)
FILE_FORMAT = (FORMAT_NAME = '{FILE_FORMAT}')
FORCE = TRUE
"""


def connect():
    """Connect as the service user with key-pair auth; settings come from env vars."""
    import snowflake.connector

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=os.getenv("SNOWFLAKE_ROLE", "LOADER"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "LOAD_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "OSS_PULSE_DEV"),
        schema="BRONZE",
    )


def load_partition(cur, p: Partition) -> int:
    """Upload and (re)load one folder. Returns the number of rows loaded."""
    cur.execute(put_sql(p))
    cur.execute("BEGIN")
    try:
        cur.execute(delete_sql(p))
        cur.execute(copy_sql(p))
        rows = sum(int(r[3]) for r in cur.fetchall())  # COPY result: column 4 = rows_loaded
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    return rows


def ensure_objects(cur) -> None:
    for sql in SETUP_SQL:
        cur.execute(sql)
