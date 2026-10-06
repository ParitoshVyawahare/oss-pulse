-- One row per release: the latest version we have extracted.

with source as (
    select * from {{ source('github', 'github_raw') }}
    where resource = 'releases'
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
    record_id::number                       as release_id,
    repo_id,
    repo_name,
    record:tag_name::string                 as tag_name,
    record:name::string                     as release_name,
    record:draft::boolean                   as is_draft,
    record:prerelease::boolean              as is_prerelease,
    record:author.login::string             as author_login,
    record:created_at::timestamp_tz         as created_at,
    record:published_at::timestamp_tz       as published_at,
    _extracted_at,
    _loaded_at
from latest
