-- BRIDGE TABLE for a many-to-many relationship: a repo has many topics, a topic has many repos.
-- Grain: one row per (repo, topic) pair, using each repo's CURRENT topics.
-- It joins on repo_id (the durable key), so it works with every version in dim_repo.

with latest_snapshot as (
    select *
    from {{ ref('stg_github__repo_snapshots') }}
    qualify row_number() over (partition by repo_id order by snapshot_at desc) = 1
),

pairs as (
    select distinct
        l.repo_id,
        lower(t.value::string) as topic
    from latest_snapshot as l,
         lateral flatten(input => l.topics) as t
)

select
    {{ dbt_utils.generate_surrogate_key(['p.repo_id', 'p.topic']) }} as repo_topic_key,
    p.repo_id,
    d.topic_key
from pairs as p
join {{ ref('dim_topic') }} as d
    on p.topic = d.topic
