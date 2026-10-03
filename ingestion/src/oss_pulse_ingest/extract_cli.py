"""Extract GitHub data for a window:

    uv run --env-file .env oss-pulse-extract --start 2026-09-01 --end 2026-10-01 --repo dbt-labs/dbt
    uv run --env-file .env oss-pulse-extract --start 2025-10-01 --end 2026-10-03   # all repos

Dates are UTC days; --end is EXCLUSIVE (the window covers start <= updated_at < end).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime

from .catalog import load_catalog_rows
from .config import CATALOG_PATH, LANDING_DIR
from .extract import RESOURCES, Window, extract
from .github_api import GitHubClient

log = logging.getLogger("oss_pulse_ingest")


def parse_day(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oss-pulse-extract", description=__doc__)
    parser.add_argument("--start", required=True, type=parse_day)
    parser.add_argument("--end", required=True, type=parse_day, help="exclusive")
    parser.add_argument("--repo", action="append", help="limit to repo(s); repeatable")
    parser.add_argument("--resource", action="append", choices=list(RESOURCES), help="default: all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    window = Window(args.start, args.end)
    repos = load_catalog_rows(CATALOG_PATH)
    if args.repo:
        wanted = {r.lower() for r in args.repo}
        repos = [r for r in repos if r["repo_name"].lower() in wanted]
        if not repos:
            parser.error(f"none of {args.repo} are in the catalog")
    resources = args.resource or list(RESOURCES)

    client = GitHubClient()
    totals = dict.fromkeys(resources, 0)
    failures = []
    for i, repo in enumerate(repos, 1):
        counts = []
        for resource in resources:
            try:
                n = extract(
                    client,
                    resource=resource,
                    repo_id=int(repo["repo_id"]),
                    repo_name=repo["repo_name"],
                    window=window,
                    landing_dir=LANDING_DIR,
                )
            except Exception as exc:  # keep going; report at the end
                log.error("%s %s failed: %s", repo["repo_name"], resource, exc)
                failures.append(f"{repo['repo_name']}:{resource}")
                continue
            totals[resource] += n
            counts.append(f"{resource}={n}")
        log.info("[%d/%d] %s  %s", i, len(repos), repo["repo_name"], " ".join(counts))

    log.info("Window %s totals: %s", window.label, totals)
    log.info("API requests used: %d", client.request_count)
    if failures:
        log.error("%d failure(s): %s", len(failures), ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
