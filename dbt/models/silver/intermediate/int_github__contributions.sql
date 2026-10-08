-- One row per contribution: a pull request opened, an issue opened, or a comment written.
-- A single place that defines "a contribution", used by dim_contributor and fct_contributions.

with pulls as (
    select
        'pr_opened'          as contribution_type,
        pull_request_id      as source_id,
        repo_id,
        author_id,
        author_login,
        author_type,
        created_at           as contributed_at
    from {{ ref('stg_github__pulls') }}
),

issues as (
    select
        'issue_opened', issue_id, repo_id, author_id, author_login, author_type, created_at
    from {{ ref('stg_github__issues') }}
),

comments as (
    select
        'comment', comment_id, repo_id, author_id, author_login, author_type, created_at
    from {{ ref('stg_github__comments') }}
),

unioned as (
    select * from pulls
    union all
    select * from issues
    union all
    select * from comments
)

select
    contribution_type || '-' || source_id    as contribution_id,
    *
from unioned
where author_id is not null   -- deleted GitHub accounts have no author
