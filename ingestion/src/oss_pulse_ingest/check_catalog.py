"""Check every repo in the catalog against the GitHub API.

    uv run --env-file .env oss-pulse-check-catalog          # report only
    uv run --env-file .env oss-pulse-check-catalog --write  # also update the CSV

For each repo we record its permanent `repo_id` and its CURRENT name, so renames
(e.g. dbt-labs/dbt-core -> dbt-labs/dbt) are caught before they silently break ingestion.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from .config import CATALOG_PATH
from .github_api import GitHubClient

log = logging.getLogger("oss_pulse_ingest")


def check(rows: list[dict], client: GitHubClient) -> tuple[list[dict], list[str]]:
    """Return updated rows plus human-readable problems."""
    updated, problems = [], []
    for row in rows:
        name = row["repo_name"].strip()
        repo = client.get_repo(name)
        if repo is None:
            problems.append(f"NOT FOUND  {name}")
            updated.append({**row, "repo_id": row.get("repo_id", "")})
            continue
        if repo["full_name"].lower() != name.lower():
            problems.append(f"RENAMED    {name} -> {repo['full_name']}")
        if repo.get("archived"):
            problems.append(f"ARCHIVED   {repo['full_name']}")
        updated.append({**row, "repo_name": repo["full_name"], "repo_id": str(repo["id"])})
    return updated, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oss-pulse-check-catalog", description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the CSV with fixes")
    parser.add_argument("--path", type=Path, default=CATALOG_PATH)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with args.path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    updated, problems = check(rows, GitHubClient())
    log.info("Checked %d repos, %d problem(s)", len(rows), len(problems))
    for p in problems:
        log.warning(p)

    if args.write:
        with args.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["repo_id", "repo_name", "category"])
            writer.writeheader()
            writer.writerows({k: r.get(k, "") for k in writer.fieldnames} for r in updated)
        log.info("Wrote %s", args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
