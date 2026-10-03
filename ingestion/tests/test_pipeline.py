import json

import pyarrow.parquet as pq
import pytest
from conftest import HOUR, write_gz
from oss_pulse_ingest.landing import BRONZE_SCHEMA
from oss_pulse_ingest.paths import manifest_path, partition_dir
from oss_pulse_ingest.pipeline import DataQualityError, ingest_hour


def test_ingest_hour_writes_parquet_and_manifest(tmp_path, sample_file, repos, opener_for):
    result = ingest_hour(
        HOUR,
        repos=repos,
        landing_dir=tmp_path / "landing",
        opener=opener_for(sample_file),
        max_malformed_ratio=0.5,
    )
    table = pq.read_table(result.output_path)
    assert table.num_rows == 3
    assert table.schema.equals(BRONZE_SCHEMA)

    manifest = json.loads(manifest_path(tmp_path / "landing", HOUR).read_text())
    assert manifest["rows_written"] == 3
    assert manifest["malformed"] == 1


def test_rerunning_an_hour_is_idempotent(tmp_path, sample_file, repos, opener_for):
    landing = tmp_path / "landing"
    for _ in range(2):
        ingest_hour(
            HOUR,
            repos=repos,
            landing_dir=landing,
            opener=opener_for(sample_file),
            max_malformed_ratio=0.5,
        )
    files = sorted(p.name for p in partition_dir(landing, HOUR).iterdir())
    assert files == ["_manifest.json", "data.parquet"]  # no duplicates, no leftover .tmp
    assert pq.read_table(partition_dir(landing, HOUR) / "data.parquet").num_rows == 3


def test_hour_with_no_matches_writes_empty_file_with_schema(tmp_path, sample_file, opener_for):
    result = ingest_hour(
        HOUR,
        repos=frozenset({"nobody/nothing"}),
        landing_dir=tmp_path,
        opener=opener_for(sample_file),
        max_malformed_ratio=0.5,
    )
    table = pq.read_table(result.output_path)
    assert table.num_rows == 0
    assert table.schema.equals(BRONZE_SCHEMA)


def test_quality_gate_rejects_corrupt_file(tmp_path, repos, opener_for):
    corrupt = write_gz(tmp_path / "bad.json.gz", ["garbage"] * 9 + ['{"repo": {"name": "x/y"}}'])
    with pytest.raises(DataQualityError):
        ingest_hour(HOUR, repos=repos, landing_dir=tmp_path, opener=opener_for(corrupt))
    assert not manifest_path(tmp_path, HOUR).exists()  # nothing landed
