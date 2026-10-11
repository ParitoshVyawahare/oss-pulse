{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- dev: use folder schemas as-is (SILVER, GOLD).
        ci:  prefix them with the PR schema (PR_8_SILVER, PR_8_GOLD), so a pull request
             can build and test everything without touching the real tables. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.name == 'ci' -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
