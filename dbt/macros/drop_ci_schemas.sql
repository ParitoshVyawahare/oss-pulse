{% macro drop_ci_schemas() %}
    {#- Drop every schema a CI run created: PR_8 itself plus PR_8_SILVER, PR_8_GOLD, ...
        Matching happens in Jinja (exact name or "<name>_" prefix), so PR_8 can never
        match PR_80. Refuses to run outside the ci target, as a safety net. -#}
    {% if target.name != 'ci' %}
        {{ exceptions.raise_compiler_error("drop_ci_schemas only runs with --target ci") }}
    {% endif %}

    {% set prefix = target.schema | upper %}
    {% set schemas = run_query(
        "select schema_name from " ~ target.database ~ ".information_schema.schemata"
    ) %}

    {% for row in schemas %}
        {% set name = row[0] | upper %}
        {% if name == prefix or name.startswith(prefix ~ "_") %}
            {% do log("Dropping schema " ~ target.database ~ "." ~ name, info=True) %}
            {% do run_query("drop schema if exists " ~ target.database ~ "." ~ name ~ " cascade") %}
        {% endif %}
    {% endfor %}
{% endmacro %}
