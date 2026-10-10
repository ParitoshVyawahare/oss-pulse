"""A thin client over MetricFlow. Every number in the dashboard comes from here.

There is deliberately NO SQL in the dashboard. Metric definitions live in one place,
dbt/models/gold/semantic/_metrics.yml, so the dashboard can never drift from them.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pandas is imported lazily, so unit tests and CI don't need it
    import pandas as pd

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"
MF = Path(sys.executable).parent / "mf"  # the mf CLI installed in the same environment


class MetricQueryError(RuntimeError):
    """MetricFlow could not answer the query."""


def build_command(
    metrics: Sequence[str],
    *,
    output_csv: Path,
    group_by: Sequence[str] = (),
    start_time: str | None = None,
    end_time: str | None = None,
    order: Sequence[str] = (),
    limit: int | None = None,
) -> list[str]:
    """Translate a metric request into an `mf query` command."""
    cmd = [str(MF), "query", "--metrics", ",".join(metrics), "--csv", str(output_csv)]
    if group_by:
        cmd += ["--group-by", ",".join(group_by)]
    if start_time:
        cmd += ["--start-time", start_time]
    if end_time:
        cmd += ["--end-time", end_time]
    if order:
        cmd += ["--order", ",".join(order)]
    if limit:
        cmd += ["--limit", str(limit)]
    return cmd


def query_metrics(metrics: Sequence[str], **kwargs) -> pd.DataFrame:
    """Run a governed-metric query and return it as a DataFrame (lowercase columns)."""
    import pandas as pd

    with tempfile.TemporaryDirectory() as tmp:
        output_csv = Path(tmp) / "result.csv"
        cmd = build_command(metrics, output_csv=output_csv, **kwargs)
        result = subprocess.run(cmd, cwd=DBT_DIR, capture_output=True, text=True)
        if result.returncode != 0 or not output_csv.exists():
            raise MetricQueryError((result.stdout + result.stderr)[-3000:])
        df = pd.read_csv(output_csv)
    df.columns = [c.lower() for c in df.columns]
    return df


def metric_catalog() -> pd.DataFrame:
    """Metric definitions straight from dbt's semantic manifest (built by `dbt parse`)."""
    import pandas as pd

    manifest_path = DBT_DIR / "target" / "semantic_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for metric in manifest.get("metrics", []):
        where_filters = (metric.get("filter") or {}).get("where_filters", [])
        rows.append(
            {
                "metric": metric["name"],
                "label": metric.get("label") or metric["name"],
                "type": str(metric.get("type", "")).lower(),
                "definition": metric.get("description") or "",
                "filter": "; ".join(f.get("where_sql_template", "") for f in where_filters),
            }
        )
    return pd.DataFrame(rows).sort_values("metric").reset_index(drop=True)
