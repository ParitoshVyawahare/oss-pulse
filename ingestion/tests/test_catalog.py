import pytest
from oss_pulse_ingest.catalog import load_catalog


def test_catalog_is_lowercased_and_deduplicated(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("repo_name,category\nDBT-Labs/dbt-core,t\ndbt-labs/dbt-core,t\n")
    assert load_catalog(path) == frozenset({"dbt-labs/dbt-core"})


def test_catalog_requires_repo_name_column(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("name\nfoo/bar\n")
    with pytest.raises(ValueError):
        load_catalog(path)
