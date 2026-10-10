FROM astrocrpublic.azurecr.io/runtime:3.3-8

# dbt gets its OWN virtual environment, so its dependencies can never clash with
# Airflow's. Cosmos runs dbt from here, and the dashboard build runs MetricFlow's
# `mf` CLI from here too (see MF_EXECUTABLE in .env).
RUN python -m venv dbt_venv && \
    dbt_venv/bin/pip install --no-cache-dir \
        "dbt-core==1.12.5" "dbt-snowflake==1.12.1" "dbt-metricflow>=0.15,<1"
