{#-
    Generic test for SCD Type 2 tables: for each entity, validity ranges must
    (1) never be empty or backwards, and
    (2) line up exactly: each version ends where the next one starts (no gaps, no overlaps).
    Returns the offending rows; the test passes when it returns nothing.
-#}
{% test no_overlapping_ranges(model, partition_by, from_column, to_column) %}

with ordered as (
    select
        {{ partition_by }}                  as entity_id,
        {{ from_column }}                   as range_from,
        {{ to_column }}                     as range_to,
        lead({{ from_column }}) over (
            partition by {{ partition_by }} order by {{ from_column }}
        )                                   as next_range_from
    from {{ model }}
)

select *
from ordered
where range_to <= range_from
   or (next_range_from is not null and range_to <> next_range_from)

{% endtest %}
