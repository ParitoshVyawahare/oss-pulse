"""Ingest one hour end to end. This is the function Airflow will call in week 2."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import MAX_MALFORMED_RATIO
from .gharchive import ParseStats, filter_and_flatten, hour_url, normalize_hour, open_url
from .landing import write_hour

Opener = Callable[[str], Iterator[bytes]]


class DataQualityError(Exception):
    """The source file looks corrupt; refuse to land it."""


@dataclass(frozen=True)
class HourResult:
    hour: datetime
    url: str
    lines_read: int
    malformed: int
    rows_written: int
    output_path: Path
    duration_seconds: float


def ingest_hour(
    hour: datetime,
    *,
    repos: frozenset[str],
    landing_dir: Path,
    opener: Opener = open_url,
    max_malformed_ratio: float = MAX_MALFORMED_RATIO,
) -> HourResult:
    """Download, filter, validate and land one hour of GH Archive data.

    `hour` decides WHICH data we fetch. We never use "now" for that: in week 2,
    Airflow passes the hour in, which is what makes backfills and reruns safe.
    (`ingested_at` does use the clock, but only as audit metadata.)

    `opener` is injectable so tests can feed a local file instead of the internet.
    """
    hour = normalize_hour(hour)
    url = hour_url(hour)
    started = time.monotonic()
    ingested_at = datetime.now(UTC)

    stats = ParseStats()
    records = list(
        filter_and_flatten(
            opener(url), repos, source_file=url, ingested_at=ingested_at, stats=stats
        )
    )

    if stats.malformed_ratio > max_malformed_ratio:
        raise DataQualityError(
            f"{url}: {stats.malformed}/{stats.lines_read} lines malformed "
            f"({stats.malformed_ratio:.2%} > {max_malformed_ratio:.2%})"
        )

    manifest = {
        "hour": hour.isoformat(),
        "source_url": url,
        "lines_read": stats.lines_read,
        "malformed": stats.malformed,
        "rows_written": len(records),
        "ingested_at": ingested_at.isoformat(),
    }
    output_path = write_hour(records, landing_dir, hour, manifest)

    return HourResult(
        hour=hour,
        url=url,
        lines_read=stats.lines_read,
        malformed=stats.malformed,
        rows_written=len(records),
        output_path=output_path,
        duration_seconds=round(time.monotonic() - started, 2),
    )
