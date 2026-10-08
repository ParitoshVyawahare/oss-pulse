-- One row per GitHub topic tag used by any tracked repo (e.g. "sql", "etl", "data-engineering").

with topics as (
    select distinct lower(t.value::string) as topic
    from {{ ref('stg_github__repo_snapshots') }} as s,
         lateral flatten(input => s.topics) as t
)

select
    {{ dbt_utils.generate_surrogate_key(['topic']) }} as topic_key,
    topic
from topics
