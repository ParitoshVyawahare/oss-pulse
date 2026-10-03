import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

HOUR = datetime(2026, 9, 21, 15, tzinfo=UTC)


def make_event(event_id: int, repo: str = "dbt-labs/dbt-core", event_type: str = "PushEvent"):
    return {
        "id": str(event_id),
        "type": event_type,
        "actor": {"id": 1000 + event_id, "login": f"user{event_id}"},
        "repo": {"id": 500, "name": repo, "url": f"https://api.github.com/repos/{repo}"},
        "payload": {"action": "opened"},
        "public": True,
        "created_at": "2026-09-21T15:04:05Z",
        "org": {"id": 9, "login": repo.split("/")[0]},
    }


def write_gz(path: Path, lines: list[str]) -> Path:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return path


@pytest.fixture
def repos() -> frozenset[str]:
    return frozenset({"dbt-labs/dbt-core", "apache/airflow"})


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """3 tracked events, 1 untracked event, 1 malformed line, 1 blank line."""
    lines = [
        json.dumps(make_event(1)),
        json.dumps(make_event(2, repo="Apache/Airflow", event_type="PullRequestEvent")),
        json.dumps(make_event(3, repo="someone/unrelated")),
        "{not valid json",
        "",
        json.dumps(make_event(4, event_type="WatchEvent")),
    ]
    return write_gz(tmp_path / "hour.json.gz", lines)


@pytest.fixture
def opener_for():
    """Return an opener that ignores the URL and reads a local file instead."""
    from oss_pulse_ingest.gharchive import open_local

    def _make(path: Path):
        return lambda _url: open_local(path)

    return _make
