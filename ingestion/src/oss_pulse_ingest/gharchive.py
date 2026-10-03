"""Read GH Archive hourly files and turn raw events into flat bronze records.

Design notes
------------
* We STREAM each file: decompress and parse line by line, never saving the
  multi-hundred-MB raw file. Memory stays flat no matter how big the hour is.
* We keep `payload` as a raw JSON string. Bronze should be a faithful copy of
  the source; parsing payloads is business logic, and that belongs in dbt.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from .config import GHARCHIVE_BASE_URL

try:  # orjson is ~5-10x faster than the stdlib for this workload
    import orjson

    def _loads(raw: bytes | str):
        return orjson.loads(raw)

    def _dumps(obj) -> str:
        return orjson.dumps(obj).decode()

except ImportError:  # pragma: no cover - fallback keeps the code runnable anywhere
    import json

    def _loads(raw: bytes | str):
        return json.loads(raw)

    def _dumps(obj) -> str:
        return json.dumps(obj, separators=(",", ":"))


class HourNotAvailableError(Exception):
    """GH Archive has no file for this hour (not published yet, or a known gap)."""


@dataclass
class ParseStats:
    lines_read: int = 0
    malformed: int = 0
    kept: int = 0

    @property
    def malformed_ratio(self) -> float:
        return self.malformed / self.lines_read if self.lines_read else 0.0


def normalize_hour(hour: datetime) -> datetime:
    """Require a timezone-aware datetime and truncate it to the start of the hour (UTC)."""
    if hour.tzinfo is None:
        raise ValueError("hour must be timezone-aware; use UTC")
    return hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def hour_url(hour: datetime) -> str:
    """GH Archive file URL. Note: the hour has NO leading zero (…-9.json.gz, not …-09)."""
    hour = normalize_hour(hour)
    return f"{GHARCHIVE_BASE_URL}/{hour:%Y-%m-%d}-{hour.hour}.json.gz"


def open_url(url: str, timeout: int = 60) -> Iterator[bytes]:
    """Stream the lines of a remote gzipped file without writing it to disk."""
    with requests.get(url, stream=True, timeout=timeout) as resp:
        if resp.status_code == 404:
            raise HourNotAvailableError(url)
        resp.raise_for_status()
        resp.raw.decode_content = False  # we decompress the .gz ourselves
        with gzip.GzipFile(fileobj=resp.raw) as gz:
            yield from gz


def open_local(path: str | Path) -> Iterator[bytes]:
    """Same interface as open_url, for local files (used by tests)."""
    with gzip.open(path, "rb") as gz:
        yield from gz


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)  # handles the trailing 'Z' on Python 3.11+
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def flatten_event(event: dict, *, source_file: str, ingested_at: datetime) -> dict:
    """Map one raw GitHub event to a flat bronze record."""
    actor = event.get("actor") or {}
    repo = event["repo"]
    org = event.get("org") or {}
    return {
        "event_id": str(event["id"]),
        "event_type": event["type"],
        "created_at": _parse_ts(event["created_at"]),
        "actor_id": actor.get("id"),
        "actor_login": actor.get("login"),
        "repo_id": repo.get("id"),
        "repo_name": repo["name"],
        "org_login": org.get("login"),
        "is_public": event.get("public"),
        "payload": _dumps(event.get("payload") or {}),
        # audit columns: where and when this row came from
        "_source_file": source_file,
        "_ingested_at": ingested_at,
    }


def filter_and_flatten(
    lines: Iterable[bytes],
    repos: frozenset[str],
    *,
    source_file: str,
    ingested_at: datetime,
    stats: ParseStats,
) -> Iterator[dict]:
    """Yield flat records for events whose repo is in the catalog.

    Malformed lines are counted, not silently dropped, so the caller can
    decide whether the hour is trustworthy.
    """
    for raw in lines:
        if not raw.strip():
            continue
        stats.lines_read += 1
        try:
            event = _loads(raw)
            repo_name = event["repo"]["name"]
        except (ValueError, KeyError, TypeError):
            stats.malformed += 1
            continue

        if repo_name.lower() not in repos:
            continue

        try:
            record = flatten_event(event, source_file=source_file, ingested_at=ingested_at)
        except (ValueError, KeyError, TypeError):
            stats.malformed += 1
            continue

        stats.kept += 1
        yield record
