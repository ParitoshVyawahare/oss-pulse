"""Write one hour of bronze records to the landing zone, idempotently.

Idempotent = running the same hour twice leaves exactly the same result.
We get that by OVERWRITING the hour's partition (never appending) and by
writing to a temp file first, then atomically renaming it into place, so a
crash mid-write can never leave a half-written file behind.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .paths import manifest_path, partition_dir

BRONZE_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("event_type", pa.string()),
        ("created_at", pa.timestamp("us", tz="UTC")),
        ("actor_id", pa.int64()),
        ("actor_login", pa.string()),
        ("repo_id", pa.int64()),
        ("repo_name", pa.string()),
        ("org_login", pa.string()),
        ("is_public", pa.bool_()),
        ("payload", pa.string()),
        ("_source_file", pa.string()),
        ("_ingested_at", pa.timestamp("us", tz="UTC")),
    ]
)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_hour(records: list[dict], landing_dir: Path, hour: datetime, manifest: dict) -> Path:
    """Write records as Parquet, then the manifest. Returns the Parquet path.

    An hour with zero matching events still gets an EMPTY file with the full
    schema. That lets us tell "processed, nothing matched" apart from
    "never processed" when we check completeness later.
    """
    target = partition_dir(landing_dir, hour)
    target.mkdir(parents=True, exist_ok=True)

    data_path = target / "data.parquet"
    tmp_path = target / "data.parquet.tmp"
    table = pa.Table.from_pylist(records, schema=BRONZE_SCHEMA)
    pq.write_table(table, tmp_path, compression="zstd")
    os.replace(tmp_path, data_path)

    # The manifest is written LAST: its presence means the hour fully succeeded.
    _atomic_write_text(
        manifest_path(landing_dir, hour), json.dumps(manifest, indent=2, default=str)
    )
    return data_path
