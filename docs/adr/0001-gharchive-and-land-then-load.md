# ADR 0001: GH Archive as the event source, and land-then-load into Snowflake

**Status:** Accepted · **Date:** 2026-10

## Context
OSS Pulse needs a high-volume, real, public event stream that behaves like product
analytics data (users performing actions over time). It also needs to load into
Snowflake, whose trial only starts in week 3.

## Decision
1. Use **GH Archive** hourly files as the event source, filtered to a curated catalog
   of data-ecosystem repos (`dbt/seeds/repo_catalog.csv`).
2. **Land first, load second.** Ingestion writes one Parquet file per hour to a local,
   Hive-partitioned landing zone. A separate step (week 3) uploads files to a Snowflake
   stage and runs `COPY INTO` the bronze tables.
3. Keep `payload` as **raw JSON** in bronze; parse it in dbt.

## Consequences
- Ingestion and loading can fail and be retried independently.
- Each hour is idempotent: reruns overwrite the hour's partition, never append.
- Raw GH Archive files are streamed and never stored, so disk usage stays small, but
  every hour still costs a full download (bandwidth is the main constraint on backfills).
- Repos are matched by name. A renamed repo silently drops out until the catalog is
  updated; the daily GitHub API DAG (week 2) will detect renames.

## Alternatives considered
- **GH Archive on BigQuery:** less bandwidth, but adds a second cloud and the free-tier
  query quota would limit backfills.
- **Synthetic SaaS events:** fully controllable, but less credible to reviewers than real data.
