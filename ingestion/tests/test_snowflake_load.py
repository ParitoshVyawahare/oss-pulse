from oss_pulse_ingest.snowflake_load import (
    Partition,
    copy_sql,
    delete_sql,
    find_partitions,
    put_sql,
)


def make_landing(tmp_path):
    root = tmp_path / "github"
    (root / "pulls" / "window=2026-09-01_2026-10-01").mkdir(parents=True)
    (root / "pulls" / "window=2026-09-01_2026-10-01" / "repo_id=1.parquet").write_bytes(b"x")
    (root / "pulls" / "window=empty").mkdir()  # no files: must be skipped
    (root / "repos" / "snapshot_date=2026-10-01").mkdir(parents=True)
    (root / "repos" / "snapshot_date=2026-10-01" / "repo_id=1.parquet").write_bytes(b"x")
    return tmp_path


def test_find_partitions_skips_empty_folders(tmp_path):
    parts = find_partitions(make_landing(tmp_path))
    assert [(p.resource, p.folder) for p in parts] == [
        ("pulls", "window=2026-09-01_2026-10-01"),
        ("repos", "snapshot_date=2026-10-01"),
    ]


def test_find_partitions_can_filter_by_resource(tmp_path):
    parts = find_partitions(make_landing(tmp_path), ["repos"])
    assert [p.resource for p in parts] == ["repos"]


def test_find_partitions_handles_missing_landing_dir(tmp_path):
    assert find_partitions(tmp_path / "nothing-here") == []


def test_sql_targets_only_its_own_folder(tmp_path):
    p = Partition("pulls", "window=2026-09-01_2026-10-01", tmp_path)
    assert "@bronze.github_landing/pulls/window=2026-09-01_2026-10-01/" in put_sql(p)
    assert "OVERWRITE = TRUE" in put_sql(p)
    assert delete_sql(p).endswith("LIKE 'pulls/window=2026-09-01_2026-10-01/%'")
    assert "FROM @bronze.github_landing/pulls/window=2026-09-01_2026-10-01/" in copy_sql(p)
    assert "FORCE = TRUE" in copy_sql(p)


def test_partitions_for_window_selects_only_that_run(tmp_path):
    from datetime import UTC, datetime

    from oss_pulse_ingest.extract import Window
    from oss_pulse_ingest.snowflake_load import partitions_for_window

    root = tmp_path / "github"
    for folder in [
        "pulls/window=2026-10-10_2026-10-11",  # this run
        "pulls/window=2026-10-09_2026-10-10",  # an earlier run
        "repos/snapshot_date=2026-10-11",  # this run's snapshot
        "repos/snapshot_date=2026-10-10",  # an earlier snapshot
    ]:
        (root / folder).mkdir(parents=True)
        (root / folder / "repo_id=1.parquet").write_bytes(b"x")

    window = Window(datetime(2026, 10, 10, tzinfo=UTC), datetime(2026, 10, 11, tzinfo=UTC))
    parts = partitions_for_window(tmp_path, window)
    assert sorted(f"{p.resource}/{p.folder}" for p in parts) == [
        "pulls/window=2026-10-10_2026-10-11",
        "repos/snapshot_date=2026-10-11",
    ]
