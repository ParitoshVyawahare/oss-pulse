-- ACCUMULATING SNAPSHOT FACT. Grain: one row per pull request, covering its whole life.
-- The row is updated as the PR moves through its milestones:
--   opened -> first response -> merged / closed
-- Each milestone has its own date key (role-playing dimension: dim_date used 4 ways).
--
-- Known limits (documented, not hidden):
--   * first response = first conversation comment by someone else who is not a bot.
--     PR review comments are not extracted yet, so some responses may be found later.
--   * our data starts in August 2026; for older PRs earlier responses are not visible.

with pulls as (
    select * from {{ ref('stg_github__pulls') }}
),

contributors as (
    select contributor_id, contributor_key, is_bot from {{ ref('dim_contributor') }}
),

first_responses as (
    select
        p.pull_request_id,
        min(c.created_at)                                  as first_response_at
    from pulls as p
    join {{ ref('stg_github__comments') }} as c
        on  c.repo_id = p.repo_id
        and c.issue_number = p.pr_number
    join contributors as cc
        on c.author_id = cc.contributor_id
    where c.author_id <> p.author_id
      and not cc.is_bot
      and c.created_at >= p.created_at
    group by p.pull_request_id
)

select
    p.pull_request_id,
    r.repo_key,
    p.repo_id,
    a.contributor_key                                      as author_contributor_key,
    to_number(to_char(p.created_at, 'YYYYMMDD'))           as created_date_key,
    to_number(to_char(fr.first_response_at, 'YYYYMMDD'))   as first_response_date_key,
    to_number(to_char(p.merged_at, 'YYYYMMDD'))            as merged_date_key,
    to_number(to_char(p.closed_at, 'YYYYMMDD'))            as closed_date_key,
    p.created_at,
    fr.first_response_at,
    p.merged_at,
    p.closed_at,
    p.state,
    p.is_draft,
    p.is_merged,
    datediff('second', p.created_at, fr.first_response_at) / 3600.0
                                                           as hours_to_first_response,
    datediff('second', p.created_at, p.merged_at) / 3600.0 as hours_to_merge
from pulls as p
join {{ ref('dim_repo') }} as r
    on  p.repo_id = r.repo_id
    and p.created_at >= r.valid_from
    and p.created_at <  r.valid_to
left join contributors as a
    on p.author_id = a.contributor_id
left join first_responses as fr
    on p.pull_request_id = fr.pull_request_id
