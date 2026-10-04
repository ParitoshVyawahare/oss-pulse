"""Make pytest import DAG files the same way Airflow does.

At runtime, Airflow adds the dags/ folder to sys.path, which is how DAGs can
`import oss_pulse_dags`. Pytest doesn't do that on its own, so we do it here.
"""

import sys
from pathlib import Path

DAGS_FOLDER = Path(__file__).resolve().parents[1] / "dags"
sys.path.insert(0, str(DAGS_FOLDER))
