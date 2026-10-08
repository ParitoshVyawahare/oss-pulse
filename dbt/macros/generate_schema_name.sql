{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- Use folder schemas as-is (SILVER, GOLD). Environments are separated by
        DATABASE (OSS_PULSE_DEV vs OSS_PULSE_PROD), so no dev_ prefix is needed. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
