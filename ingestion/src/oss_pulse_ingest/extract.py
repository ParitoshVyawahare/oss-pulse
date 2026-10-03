"""Extract GitHub API data for one time window and land it as raw-JSON Parquet.

The core idea: INCREMENTAL extraction by `updated_at`.
Each run asks only for records that changed inside a window [start, end).
* Initial backfill: one big window, e.g. 2025-10-01 -> 2026-10-01.
* Daily runs (Airflow, week 2): one-day windows, e.g. 2026-10-03 -> 2026-10-04.
A record that changes again later (a PR gets merged) simply shows up in a later
window; dbt keeps the latest version of each record (incremental merge, week 3).

We store each record as RAW JSON plus a few metadata columns. Parsing happens in
Snowflake/dbt (ELT), so if we need a new field later, it's already in bronze.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .github_api import GitHubClient

RAW_SCHEMA = pa.schema(
    [
        ("resource", pa.string()),
        ("repo_id", pa.int64()),
        ("repo_name", pa.string()),
        ("record_id", pa.string()),
        ("record_updated_at", pa.timestamp("us", tz="UTC")),
        ("record", pa.string()),  # the full API object as JSON
        ("_window_start", pa.timestamp("us", tz="UTC")),
        ("_window_end", pa.timestamp("us", tz="UTC")),
        ("_extracted_at", pa.timestamp("us", tz="UTC")),
    ]
)


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime  # exclusive

    def __post_init__(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("window bounds must be timezone-aware (UTC)")
        if self.end <= self.start:
            raise ValueError("window end must be after start")

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m-%d}_{self.end:%Y-%m-%d}"


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- one iterator per resource ---------------------------------------------------
# Each yields raw API objects that changed inside the window.


def iter_pulls(client: GitHubClient, repo: str, window: Window) -> Iterator[dict]:
    """The pulls endpoint has no `since` filter, so we sort newest-updated first
    and STOP as soon as we pass the window start. Without that early stop, every
    daily run would page through a repo's entire PR history."""
    params = {"state": "all", "sort": "updated", "direction": "desc"}
    for pr in client.paginate(f"repos/{repo}/pulls", params):
        updated = ts(pr["updated_at"])
        if updated < window.start:
            break
        if updated < window.end:
            yield pr


def iter_issues(client: GitHubClient, repo: str, window: Window) -> Iterator[dict]:
    """GitHub's issues endpoint also returns PRs (every PR is an issue under the hood).
    We skip those, since iter_pulls already covers PRs with richer fields."""
    params = {
        "state": "all",
        "sort": "updated",
        "direction": "asc",
        "since": iso(window.start),
    }
    for issue in client.paginate(f"repos/{repo}/issues", params):
        if ts(issue["updated_at"]) >= window.end:
            break
        if "pull_request" in issue:
            continue
        yield issue


def iter_comments(client: GitHubClient, repo: str, window: Window) -> Iterator[dict]:
    """All issue and PR conversation comments in the repo, oldest-updated first."""
    params = {"sort": "updated", "direction": "asc", "since": iso(window.start)}
    for comment in client.paginate(f"repos/{repo}/issues/comments", params):
        if ts(comment["updated_at"]) >= window.end:
            break
        yield comment


def iter_releases(client: GitHubClient, repo: str, window: Window) -> Iterator[dict]:
    """Releases have no `since` filter and no guaranteed sort order, so we read
    them all and filter. Release lists are short, so this stays cheap."""
    for release in client.paginate(f"repos/{repo}/releases"):
        if window.start <= ts(release["created_at"]) < window.end:
            yield release


def iter_repo(client: GitHubClient, repo: str, window: Window) -> Iterator[dict]:
    """Current repo metadata: a daily SNAPSHOT that dbt turns into SCD Type 2."""
    data = client.get_repo(repo)
    if data is not None:
        yield data


RESOURCES: dict[str, Callable[[GitHubClient, str, Window], Iterator[dict]]] = {
    "repos": iter_repo,
    "pulls": iter_pulls,
    "issues": iter_issues,
    "comments": iter_comments,
    "releases": iter_releases,
}


def record_updated_at(resource: str, record: dict) -> datetime:
    if resource == "releases":  # releases have no updated_at
        return ts(record.get("published_at") or record["created_at"])
    return ts(record["updated_at"])


def partition_path(landing_dir: Path, resource: str, window: Window, repo_id: int) -> Path:
    """github/pulls/window=2026-10-03_2026-10-04/repo_id=53548867.parquet

    One file per (resource, window, repo). Rerunning the same window overwrites
    the same file, which makes every run idempotent.
    Repo snapshots are keyed by the day they were taken instead of a window.
    """
    if resource == "repos":
        folder = f"snapshot_date={window.end:%Y-%m-%d}"
    else:
        folder = f"window={window.label}"
    return landing_dir / "github" / resource / folder / f"repo_id={repo_id}.parquet"


def write_records(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=RAW_SCHEMA), tmp, compression="zstd")
    os.replace(tmp, path)


def extract(
    client: GitHubClient,
    *,
    resource: str,
    repo_id: int,
    repo_name: str,
    window: Window,
    landing_dir: Path,
) -> int:
    """Extract one resource for one repo and window. Returns the number of records."""
    extracted_at = datetime.now(UTC)
    rows = [
        {
            "resource": resource,
            "repo_id": repo_id,
            "repo_name": repo_name,
            "record_id": str(record["id"]),
            "record_updated_at": record_updated_at(resource, record),
            "record": json.dumps(record, separators=(",", ":")),
            "_window_start": window.start,
            "_window_end": window.end,
            "_extracted_at": extracted_at,
        }
        for record in RESOURCES[resource](client, repo_name, window)
    ]
    write_records(rows, partition_path(landing_dir, resource, window, repo_id))
    return len(rows)
