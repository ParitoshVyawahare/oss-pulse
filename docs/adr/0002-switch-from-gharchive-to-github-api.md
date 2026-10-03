# ADR 0002: Switch the event source from GH Archive to the GitHub REST API

**Status:** Accepted · **Date:** 2026-10-03 · **Supersedes:** the source choice in ADR 0001

## Context
ADR 0001 chose GH Archive hourly files as the event source. Before building any
downstream models, we profiled one real hour and compared it to the same hour two
years earlier:

| Hour (UTC)       | Total events | PullRequestEvent | WatchEvent | PushEvent |
|------------------|-------------:|-----------------:|-----------:|----------:|
| 2024-09-23 15:00 | ~265,000     | 21,157           | 9,176      | 149,346   |
| 2026-09-21 15:00 | ~2,350       | 917              | 172        | 0         |

GitHub changed its public Events API in October 2025, and the GH Archive feed now
captures roughly 1% of public activity. Metrics built on it (PR counts, merge rates,
contributor counts) would be wrong by orders of magnitude.

## Decision
Extract directly from the **GitHub REST API** for the curated repo catalog:
repo metadata, pull requests, issues, issue/PR comments, and releases.

- **Incremental by `updated_at` windows** `[start, end)`: a backfill uses large windows;
  daily runs (Airflow) use one-day windows.
- **Raw JSON landing:** each record is stored unparsed with metadata columns
  (`resource`, `repo_id`, `record_id`, `record_updated_at`, window bounds,
  `_extracted_at`), one Parquet file per (resource, window, repo). Parsing happens in
  Snowflake/dbt (ELT).
- **Repo snapshots** are taken daily and become SCD Type 2 history via a dbt snapshot.
- The catalog stores the permanent `repo_id`; `oss-pulse-check-catalog` detects renames,
  archived repos, and deleted repos.

## Consequences
- Complete, current data: one month for 64 repos is ~170k records (~2,600 API requests).
- The API returns only each record's **current state**. A record that changes again
  appears in a later window; dbt keeps the latest version (incremental merge).
- Bounded by the 5,000 requests/hour limit: an 11-month backfill is roughly 6 hours,
  handled by automatic rate-limit waits and month-by-month Airflow backfills.
- The client must handle real API behavior: pagination, rate limits, HTTP 5xx, network
  timeouts, and redirects for renamed repos. Each is covered by a unit test.
- Some Apache projects track issues in JIRA, so issue metrics are not comparable across
  all repos; this is documented on the dashboard.
- The GH Archive ingestion code is removed.
