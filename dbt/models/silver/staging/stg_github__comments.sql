-- One row per comment on an issue or pull request: the latest version we have extracted.
-- Comment text is intentionally left out: no metric needs it, and it keeps the model small.

with source as (
    select * from {{ source('github', 'github_raw') }}
    where resource = 'comments'
),

latest as (
    select *
    from source
    qualify row_number() over (
        partition by record_id
        order by record_updated_at desc, _extracted_at desc
    ) = 1
)

select
    record_id::number                       as comment_id,
    repo_id,
    repo_name,
    -- issue_url ends in /issues/<number>. On GitHub every PR is also an issue,
    -- so this number matches either an issue or a pull request.
    split_part(record:issue_url::string, '/', -1)::number
                                            as issue_number,
    record:user.id::number                  as author_id,
    record:user.login::string               as author_login,
    record:user.type::string                as author_type,
    coalesce(record:user.type::string = 'Bot', false)
        or coalesce(record:user.login::string ilike '%[bot]', false)
                                            as is_bot_author,
    record:author_association::string       as author_association,
    record:created_at::timestamp_tz         as created_at,
    record:updated_at::timestamp_tz         as updated_at,
    _extracted_at,
    _loaded_at
from latest
