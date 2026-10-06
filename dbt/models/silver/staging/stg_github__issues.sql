-- One row per issue (pull requests excluded): the latest version we have extracted.

with source as (
    select * from {{ source('github', 'github_raw') }}
    where resource = 'issues'
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
    record_id::number                       as issue_id,
    repo_id,
    repo_name,
    record:number::number                   as issue_number,
    record:title::string                    as title,
    record:state::string                    as state,
    record:state_reason::string             as state_reason,
    record:user.id::number                  as author_id,
    record:user.login::string               as author_login,
    record:user.type::string                as author_type,
    coalesce(record:user.type::string = 'Bot', false)
        or coalesce(record:user.login::string ilike '%[bot]', false)
                                            as is_bot_author,
    record:author_association::string       as author_association,
    record:comments::number                 as comment_count,
    record:created_at::timestamp_tz         as created_at,
    record:updated_at::timestamp_tz         as updated_at,
    record:closed_at::timestamp_tz          as closed_at,
    _extracted_at,
    _loaded_at
from latest
