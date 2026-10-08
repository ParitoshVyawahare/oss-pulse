-- TRANSACTION FACT. Grain: one row per contribution (PR opened, issue opened, comment).
-- INCREMENTAL: the first run builds everything; later runs only process recent rows and
-- MERGE them in by contribution_id, so reruns never create duplicates.
-- is_bot is deliberately NOT stored here: it lives in dim_contributor, so updating the
-- known_bots list fixes every metric without rebuilding this table.

{{ config(
    materialized='incremental',
    unique_key='contribution_id',
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
) }}

with contributions as (
    select * from {{ ref('int_github__contributions') }}
    {% if is_incremental() %}
    -- Lookback window: re-check the last 3 days so late-arriving data is not missed.
    where contributed_at >= (select dateadd('day', -3, max(contributed_at)) from {{ this }})
    {% endif %}
)

select
    c.contribution_id,
    c.contribution_type,
    c.source_id,
    r.repo_key,
    c.repo_id,
    ct.contributor_key,
    to_number(to_char(c.contributed_at, 'YYYYMMDD'))   as date_key,
    c.contributed_at
from contributions as c
-- Point-in-time join: the repo VERSION that was valid when the contribution happened.
join {{ ref('dim_repo') }} as r
    on  c.repo_id = r.repo_id
    and c.contributed_at >= r.valid_from
    and c.contributed_at <  r.valid_to
join {{ ref('dim_contributor') }} as ct
    on c.author_id = ct.contributor_id
