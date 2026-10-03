.PHONY: install test lint check-catalog extract-month

install:  ## install dependencies and git hooks
	uv sync
	uv run pre-commit install

test:  ## run unit tests
	uv run pytest -q

lint:  ## lint and format-check python
	uv run ruff check .
	uv run ruff format --check .

check-catalog:  ## validate repo names and IDs against the GitHub API
	uv run --env-file .env oss-pulse-check-catalog

extract-month:  ## extract one month for all repos, e.g. make extract-month START=2026-09-01 END=2026-10-01
	uv run --env-file .env oss-pulse-extract --start $(START) --end $(END)
