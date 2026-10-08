-- SCD Type 1: one row per contributor (person or bot). If someone renames their account,
-- we simply overwrite the login with the latest one; no history is kept.
-- is_bot here is THE bot flag for the whole project: GitHub's rule + the known_bots list.

with contributions as (
    select * from {{ ref('int_github__contributions') }}
),

known_bots as (
    select lower(login) as login, reason from {{ ref('known_bots') }}
),

latest_identity as (
    -- SCD1: keep only the most recent login and account type per contributor.
    select author_id, author_login, author_type
    from contributions
    qualify row_number() over (partition by author_id order by contributed_at desc) = 1
),

activity as (
    select
        author_id,
        min(contributed_at)        as first_seen_at,
        max(contributed_at)        as last_seen_at,
        count(*)                   as total_contributions,
        count(distinct repo_id)    as repos_contributed_to
    from contributions
    group by author_id
),

classified as (
    select
        l.*,
        coalesce(l.author_type = 'Bot', false)
            or coalesce(l.author_login ilike '%[bot]', false)  as is_bot_by_rule,
        kb.login is not null                                   as is_bot_by_review,
        kb.reason                                              as bot_review_reason
    from latest_identity as l
    left join known_bots as kb
        on lower(l.author_login) = kb.login
)

select
    {{ dbt_utils.generate_surrogate_key(['c.author_id']) }}    as contributor_key,
    c.author_id                                               as contributor_id,
    c.author_login                                            as login,
    c.author_type                                             as account_type,
    c.is_bot_by_rule or c.is_bot_by_review                    as is_bot,
    case
        when c.is_bot_by_rule   then 'github_rule'
        when c.is_bot_by_review then 'known_bots_list'
    end                                                       as bot_detection_source,
    c.bot_review_reason,
    a.first_seen_at,
    a.last_seen_at,
    a.total_contributions,
    a.repos_contributed_to
from classified as c
join activity as a on c.author_id = a.author_id
