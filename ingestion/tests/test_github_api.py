import pytest
from oss_pulse_ingest.check_catalog import check
from oss_pulse_ingest.github_api import GitHubAPIError, GitHubClient


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, next_url=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.links = {"next": {"url": next_url}} if next_url else {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    """Returns queued responses in order and records the URLs requested."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.urls = []

    def get(self, url, params=None, timeout=None):
        self.urls.append(url)
        return self.responses.pop(0)


def make_client(responses):
    session = FakeSession(responses)
    waits = []
    client = GitHubClient("t", session=session, sleep=waits.append)
    return client, session, waits


def test_missing_token_fails_clearly(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GitHubAPIError):
        GitHubClient()


def test_paginate_follows_next_links():
    client, session, _ = make_client(
        [
            FakeResponse(body=[{"n": 1}, {"n": 2}], next_url="https://api.github.com/page2"),
            FakeResponse(body=[{"n": 3}]),
        ]
    )
    assert [i["n"] for i in client.paginate("repos/a/b/pulls")] == [1, 2, 3]
    assert session.urls[1] == "https://api.github.com/page2"


def test_retries_server_errors_with_backoff():
    client, _, waits = make_client([FakeResponse(status=502), FakeResponse(body={"ok": True})])
    assert client.get("x").json() == {"ok": True}
    assert waits == [2]


def test_waits_when_rate_limited():
    client, _, waits = make_client(
        [FakeResponse(status=429, headers={"retry-after": "7"}), FakeResponse(body={})]
    )
    client.get("x")
    assert waits == [7.0]


def test_check_catalog_flags_renames_and_missing_repos():
    client, _, _ = make_client(
        [
            FakeResponse(body={"id": 53548867, "full_name": "dbt-labs/dbt", "archived": False}),
            FakeResponse(status=404),
        ]
    )
    rows = [
        {"repo_name": "dbt-labs/dbt-core", "category": "transformation"},
        {"repo_name": "gone/repo", "category": "bi"},
    ]
    updated, problems = check(rows, client)
    assert updated[0]["repo_name"] == "dbt-labs/dbt"
    assert updated[0]["repo_id"] == "53548867"
    assert any("RENAMED" in p for p in problems)
    assert any("NOT FOUND" in p for p in problems)
