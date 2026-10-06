"""Load landed files into Snowflake BRONZE:

uv run --env-file .env oss-pulse-load                      # every landing folder
uv run --env-file .env oss-pulse-load --resource pulls     # one resource
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import LANDING_DIR
from .extract import RESOURCES
from .snowflake_load import connect, ensure_objects, find_partitions, load_partition

log = logging.getLogger("oss_pulse_ingest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oss-pulse-load", description=__doc__)
    parser.add_argument("--resource", action="append", choices=list(RESOURCES))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    partitions = find_partitions(LANDING_DIR, args.resource)
    if not partitions:
        log.error("No landing files found under %s", LANDING_DIR / "github")
        return 1
    log.info("Loading %d landing folders into Snowflake", len(partitions))

    conn = connect()
    try:
        cur = conn.cursor()
        ensure_objects(cur)
        total = 0
        for i, p in enumerate(partitions, 1):
            rows = load_partition(cur, p)
            total += rows
            log.info("[%d/%d] %s/%s  rows=%d", i, len(partitions), p.resource, p.folder, rows)
        log.info("Done: %d rows loaded", total)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
