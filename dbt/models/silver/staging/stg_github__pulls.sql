-- One row per pull request: the latest version we have extracted.

with source as (
    select * from {{ source('github', 'github_raw') }}
    where resource = 'pulls'
),

latest as (
    -- A PR is extracted again every time it changes (e.g. when it gets merged).
    -- Keep only its most recent version.
    select *
    from source
    qualify row_number() over (
        partition by record_id
        order by record_updated_at desc, _extracted_at desc
    ) = 1
)

select
    record_id::number                       as pull_request_id,
    repo_id,
    repo_name,
    record:number::number                   as pr_number,
    record:title::string                    as title,
    record:state::string                    as state,
    record:draft::boolean                   as is_draft,
    record:user.id::number                  as author_id,
    record:user.login::string               as author_login,
    record:user.type::string                as author_type,
    coalesce(record:user.type::string = 'Bot', false)
        or coalesce(record:user.login::string ilike '%[bot]', false)
                                            as is_bot_author,
    record:created_at::timestamp_tz         as created_at,
    record:updated_at::timestamp_tz         as updated_at,
    record:closed_at::timestamp_tz          as closed_at,
    record:merged_at::timestamp_tz          as merged_at,
    merged_at is not null                   as is_merged,
    _extracted_at,
    _loaded_at
from latest
