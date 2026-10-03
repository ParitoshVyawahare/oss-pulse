"""Load the curated list of repositories we track.

The catalog lives in dbt/seeds/ so ingestion (which repos to keep) and dbt
(how repos are categorized) read the SAME file: one source of truth.
"""

import csv
from pathlib import Path


def load_catalog(path: Path) -> frozenset[str]:
    """Return lowercase 'owner/repo' names. GitHub names are case-insensitive."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "repo_name" not in (reader.fieldnames or []):
            raise ValueError(f"{path} must have a 'repo_name' column")
        repos = {row["repo_name"].strip().lower() for row in reader if row["repo_name"].strip()}

    if not repos:
        raise ValueError(f"{path} contains no repositories")
    return frozenset(repos)


def load_catalog_rows(path: Path) -> list[dict]:
    """Full catalog rows (repo_id, repo_name, category), for the API extractor."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("repo_name", "").strip()]
    missing_ids = [r["repo_name"] for r in rows if not r.get("repo_id")]
    if missing_ids:
        raise ValueError(
            f"Run oss-pulse-check-catalog --write first; missing repo_id: {missing_ids}"
        )
    return rows
