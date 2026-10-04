from datetime import UTC, datetime

import pyarrow.parquet as pq
import pytest
from oss_pulse_ingest.extract import (
    Window,
    extract,
    iter_comments,
    iter_issues,
    iter_pulls,
    iter_releases,
    partition_path,
)

WINDOW = Window(datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC))


class FakeClient:
    """Serves canned lists per endpoint and counts how many items were consumed."""

    def __init__(self, data):
        self.data = data
        self.consumed = 0
        self.params = {}

    def paginate(self, path, params=None):
        self.params[path] = params
        for item in self.data.get(path, []):
            self.consumed += 1
            yield item

    def get_repo(self, name):
        return self.data.get("repo")


def test_window_requires_utc_and_order():
    with pytest.raises(ValueError):
        Window(datetime(2026, 9, 1), datetime(2026, 10, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        Window(WINDOW.end, WINDOW.start)


def test_pulls_keep_window_and_stop_early():
    pulls = [  # sorted newest-updated first, like the API
        {"id": 1, "updated_at": "2026-10-02T00:00:00Z"},  # after window: skip
        {"id": 2, "updated_at": "2026-09-20T00:00:00Z"},  # inside
        {"id": 3, "updated_at": "2026-09-01T00:00:00Z"},  # inside (start is inclusive)
        {"id": 4, "updated_at": "2026-08-31T23:59:59Z"},  # before window: STOP here
        {"id": 5, "updated_at": "2026-08-01T00:00:00Z"},  # must never be read
    ]
    client = FakeClient({"repos/a/b/pulls": pulls})
    assert [p["id"] for p in iter_pulls(client, "a/b", WINDOW)] == [2, 3]
    assert client.consumed == 4  # stopped without reading item 5


def test_issues_skip_pull_requests_and_stop_at_window_end():
    issues = [  # sorted oldest-updated first
        {"id": 1, "updated_at": "2026-09-02T00:00:00Z"},
        {"id": 2, "updated_at": "2026-09-03T00:00:00Z", "pull_request": {}},
        {"id": 3, "updated_at": "2026-10-01T00:00:00Z"},  # end is exclusive: stop
    ]
    client = FakeClient({"repos/a/b/issues": issues})
    assert [i["id"] for i in iter_issues(client, "a/b", WINDOW)] == [1]
    assert client.params["repos/a/b/issues"]["since"] == "2026-09-01T00:00:00Z"


def test_comments_stop_at_window_end():
    comments = [
        {"id": 1, "updated_at": "2026-09-05T00:00:00Z"},
        {"id": 2, "updated_at": "2026-10-05T00:00:00Z"},
    ]
    client = FakeClient({"repos/a/b/issues/comments": comments})
    assert [c["id"] for c in iter_comments(client, "a/b", WINDOW)] == [1]


def test_releases_filter_by_created_at():
    releases = [
        {"id": 1, "created_at": "2026-09-15T00:00:00Z"},
        {"id": 2, "created_at": "2026-07-01T00:00:00Z"},
    ]
    client = FakeClient({"repos/a/b/releases": releases})
    assert [r["id"] for r in iter_releases(client, "a/b", WINDOW)] == [1]


def test_extract_writes_raw_json_idempotently(tmp_path):
    client = FakeClient(
        {"repos/a/b/pulls": [{"id": 7, "updated_at": "2026-09-10T00:00:00Z", "title": "x"}]}
    )
    for _ in range(2):  # run twice: same single file, same rows
        n = extract(
            client,
            resource="pulls",
            repo_id=42,
            repo_name="a/b",
            window=WINDOW,
            landing_dir=tmp_path,
        )
        client.consumed = 0
    path = partition_path(tmp_path, "pulls", WINDOW, 42)
    table = pq.read_table(path)
    assert n == 1
    assert table.num_rows == 1
    assert table.column("record_id").to_pylist() == ["7"]
    assert '"title":"x"' in table.column("record").to_pylist()[0]
    assert sorted(p.name for p in path.parent.iterdir()) == ["repo_id=42.parquet"]


def test_window_from_scheduled_interval_is_used_as_is():
    start = datetime(2026, 10, 3, tzinfo=UTC)
    end = datetime(2026, 10, 4, tzinfo=UTC)
    assert Window.from_interval(start, end) == Window(start, end)


def test_window_from_manual_run_becomes_previous_full_day():
    moment = datetime(2026, 10, 4, 16, 45, 53, tzinfo=UTC)  # manual run: start == end
    window = Window.from_interval(moment, moment)
    assert window.start == datetime(2026, 10, 3, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 4, tzinfo=UTC)
