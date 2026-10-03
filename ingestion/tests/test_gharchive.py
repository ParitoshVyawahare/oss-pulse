from datetime import UTC, datetime

import pytest
from conftest import HOUR
from oss_pulse_ingest.gharchive import (
    ParseStats,
    filter_and_flatten,
    hour_url,
    normalize_hour,
    open_local,
)


def test_hour_url_has_no_leading_zero():
    assert hour_url(datetime(2026, 9, 1, 9, tzinfo=UTC)).endswith("/2026-09-01-9.json.gz")


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        normalize_hour(datetime(2026, 9, 1, 9))


def test_normalize_truncates_to_hour():
    assert normalize_hour(datetime(2026, 9, 1, 9, 42, 7, tzinfo=UTC)) == datetime(
        2026, 9, 1, 9, tzinfo=UTC
    )


def test_filter_keeps_only_catalog_repos_case_insensitively(sample_file, repos):
    stats = ParseStats()
    records = list(
        filter_and_flatten(
            open_local(sample_file), repos, source_file="x", ingested_at=HOUR, stats=stats
        )
    )
    assert [r["event_id"] for r in records] == ["1", "2", "4"]
    assert stats.lines_read == 5  # blank line is not counted
    assert stats.malformed == 1
    assert stats.kept == 3


def test_flattened_record_shape(sample_file, repos):
    record = next(
        filter_and_flatten(
            open_local(sample_file), repos, source_file="src", ingested_at=HOUR, stats=ParseStats()
        )
    )
    assert record["repo_name"] == "dbt-labs/dbt-core"
    assert record["actor_login"] == "user1"
    assert record["created_at"] == datetime(2026, 9, 21, 15, 4, 5, tzinfo=UTC)
    assert isinstance(record["payload"], str)  # raw JSON kept for dbt to parse
    assert record["_source_file"] == "src"
