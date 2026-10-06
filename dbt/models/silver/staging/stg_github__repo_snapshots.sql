-- One row per repo per day we looked at it. Unlike the other staging models we KEEP
-- history here: these snapshots become the SCD Type 2 repo dimension in week 4.
-- The snapshot date is when we captured the data (_extracted_at), not a folder label.

with source as (
    select * from {{ source('github', 'github_raw') }}
    where resource = 'repos'
),

one_per_day as (
    select *
    from source
    qualify row_number() over (
        partition by repo_id, to_date(_extracted_at)
        order by _extracted_at desc
    ) = 1
)

select
    repo_id || '-' || to_char(to_date(_extracted_at), 'YYYYMMDD')
                                            as repo_snapshot_key,
    repo_id,
    record:full_name::string                as repo_name,
    record:owner.login::string              as owner_login,
    record:owner.type::string               as owner_type,
    record:description::string              as description,
    record:language::string                 as primary_language,
    record:license.spdx_id::string          as license_spdx_id,
    record:topics::array                    as topics,
    record:archived::boolean                as is_archived,
    record:fork::boolean                    as is_fork,
    record:default_branch::string           as default_branch,
    record:stargazers_count::number         as stars,
    record:forks_count::number              as forks,
    record:open_issues_count::number        as open_issues_and_prs,
    record:created_at::timestamp_tz         as repo_created_at,
    record:pushed_at::timestamp_tz          as last_pushed_at,
    _extracted_at                           as snapshot_at,
    to_date(_extracted_at)                  as snapshot_date
from one_per_day
