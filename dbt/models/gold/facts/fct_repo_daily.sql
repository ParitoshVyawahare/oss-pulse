-- PERIODIC SNAPSHOT FACT. Grain: one row per repo per day we captured it.
-- Stars and forks change daily, so they are measures here, not attributes in dim_repo.

with snapshots as (
    select * from {{ ref('stg_github__repo_snapshots') }}
)

select
    s.repo_snapshot_key,
    r.repo_key,
    s.repo_id,
    to_number(to_char(s.snapshot_date, 'YYYYMMDD'))         as date_key,
    s.snapshot_date,
    s.stars,
    s.forks,
    s.open_issues_and_prs,
    s.stars - lag(s.stars) over (partition by s.repo_id order by s.snapshot_date)
                                                            as stars_gained_since_previous
from snapshots as s
join {{ ref('dim_repo') }} as r
    on  s.repo_id = r.repo_id
    and s.snapshot_at >= r.valid_from
    and s.snapshot_at <  r.valid_to
