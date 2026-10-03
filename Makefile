.PHONY: install test lint ingest-hour ingest-week

install:  ## install dependencies and git hooks
	uv sync
	uv run pre-commit install

test:  ## run unit tests
	uv run pytest -q

lint:  ## lint and format-check python
	uv run ruff check .
	uv run ruff format --check .

ingest-hour:  ## ingest a single hour (smoke test)
	uv run oss-pulse-ingest --start 2026-09-21T15

ingest-week:  ## ingest 7 days; safe to stop and rerun
	uv run oss-pulse-ingest --start 2026-09-21T00 --end 2026-09-27T23 --skip-existing
