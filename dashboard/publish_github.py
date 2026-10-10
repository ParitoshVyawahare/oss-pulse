"""Publish one file to a GitHub repo through the Contents API.

Used by Airflow to refresh docs/index.html on GitHub Pages. Going through the API
(instead of `git push`) means the local working copy, and whatever branch you are on,
is never touched. The token only needs Contents: read & write on this one repo.
"""

from __future__ import annotations

import base64
from pathlib import Path

import requests

API_URL = "https://api.github.com"


def publish_file(
    local_path: Path,
    *,
    repo: str,
    path_in_repo: str,
    token: str,
    branch: str = "main",
    message: str = "chore: refresh public dashboard [skip ci]",
    session: requests.Session | None = None,
) -> str:
    """Create or update the file. Returns 'created', 'updated' or 'unchanged'."""
    session = session or requests.Session()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{API_URL}/repos/{repo}/contents/{path_in_repo}"
    new_content = local_path.read_bytes()

    current = session.get(url, headers=headers, params={"ref": branch}, timeout=30)
    if current.status_code == 404:
        sha = None
    else:
        current.raise_for_status()
        body = current.json()
        sha = body["sha"]
        if base64.b64decode(body.get("content", "")) == new_content:
            return "unchanged"  # no empty commits

    payload = {
        "message": message,
        "content": base64.b64encode(new_content).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha  # required by GitHub to update an existing file
    session.put(url, headers=headers, json=payload, timeout=30).raise_for_status()
    return "updated" if sha else "created"
