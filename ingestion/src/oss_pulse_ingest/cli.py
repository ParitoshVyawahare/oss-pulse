"""Command line entry point:

uv run oss-pulse-ingest --start 2026-09-21T00 --end 2026-09-27T23 --skip-existing
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from .catalog import load_catalog
from .config import CATALOG_PATH, LANDING_DIR
from .gharchive import HourNotAvailableError
from .paths import manifest_path
from .pipeline import DataQualityError, ingest_hour

log = logging.getLogger("oss_pulse_ingest")


def parse_hour(value: str) -> datetime:
    """'2026-09-21T15' -> 2026-09-21 15:00 UTC"""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DDTHH, got {value!r}") from exc


def iter_hours(start: datetime, end: datetime) -> Iterator[datetime]:
    """Every hour from start to end, inclusive."""
    if end < start:
        raise ValueError("end must not be before start")
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oss-pulse-ingest", description=__doc__)
    parser.add_argument("--start", required=True, type=parse_hour, help="UTC hour, YYYY-MM-DDTHH")
    parser.add_argument("--end", type=parse_hour, help="inclusive UTC hour (default: --start)")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip hours that already have a manifest (resume an interrupted run)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    repos = load_catalog(CATALOG_PATH)
    log.info("Tracking %d repos; landing to %s", len(repos), LANDING_DIR)

    failures: list[str] = []
    for hour in iter_hours(args.start, args.end or args.start):
        label = f"{hour:%Y-%m-%dT%H}"
        if args.skip_existing and manifest_path(LANDING_DIR, hour).exists():
            log.info("%s skipped (already landed)", label)
            continue
        try:
            r = ingest_hour(hour, repos=repos, landing_dir=LANDING_DIR)
        except HourNotAvailableError:
            log.warning("%s not available on GH Archive", label)
            failures.append(label)
            continue
        except DataQualityError as exc:
            log.error("%s failed quality gate: %s", label, exc)
            failures.append(label)
            continue
        log.info(
            "%s read=%d kept=%d malformed=%d in %.1fs",
            label,
            r.lines_read,
            r.rows_written,
            r.malformed,
            r.duration_seconds,
        )

    if failures:
        log.error("%d hour(s) failed: %s", len(failures), ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
