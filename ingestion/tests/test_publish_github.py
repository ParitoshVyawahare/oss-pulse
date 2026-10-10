import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard"))

from publish_github import publish_file  # noqa: E402


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, get_response):
        self.get_response = get_response
        self.puts = []

    def get(self, url, headers=None, params=None, timeout=None):
        return self.get_response

    def put(self, url, headers=None, json=None, timeout=None):
        self.puts.append(json)
        return FakeResponse(200)


def _publish(tmp_path, session, content=b"<html>new</html>"):
    page = tmp_path / "index.html"
    page.write_bytes(content)
    return publish_file(
        page, repo="me/repo", path_in_repo="docs/index.html", token="t", session=session
    )


def test_creates_file_when_missing(tmp_path):
    session = FakeSession(FakeResponse(404))
    assert _publish(tmp_path, session) == "created"
    assert "sha" not in session.puts[0]


def test_updates_with_sha_when_changed(tmp_path):
    old = base64.b64encode(b"<html>old</html>").decode()
    session = FakeSession(FakeResponse(200, {"sha": "abc", "content": old}))
    assert _publish(tmp_path, session) == "updated"
    assert session.puts[0]["sha"] == "abc"
    assert base64.b64decode(session.puts[0]["content"]) == b"<html>new</html>"


def test_skips_commit_when_unchanged(tmp_path):
    same = base64.b64encode(b"<html>new</html>").decode()
    session = FakeSession(FakeResponse(200, {"sha": "abc", "content": same}))
    assert _publish(tmp_path, session) == "unchanged"
    assert session.puts == []
