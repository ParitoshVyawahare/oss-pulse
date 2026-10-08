-- SCD Type 2: one row per VERSION of a repo. A new version starts whenever a tracked
-- attribute changes. Stars and forks are NOT tracked here: they change daily, so they
-- live in fct_repo_daily as measures.

with snapshots as (
    select
        repo_id,
        snapshot_at,
        repo_name,
        owner_login,
        owner_type,
        primary_language,
        license_spdx_id,
        is_archived,
        is_fork,
        default_branch,
        -- Fingerprint of the tracked attributes: if it changes, a new version starts.
        hash(repo_name, owner_login, primary_language, license_spdx_id,
             is_archived, default_branch)                  as attributes_hash
    from {{ ref('stg_github__repo_snapshots') }}
),

compared as (
    select
        *,
        lag(attributes_hash) over (partition by repo_id order by snapshot_at)
                                                            as previous_hash
    from snapshots
),

versions as (
    -- Keep only the first snapshot of each new version.
    select *
    from compared
    where previous_hash is null or attributes_hash <> previous_hash
),

dated as (
    select
        *,
        -- We don't know history before our first capture, so the first known
        -- version is assumed to have always been true.
        case when previous_hash is null
             then '1900-01-01'::timestamp_tz
             else snapshot_at
        end                                                 as valid_from,
        coalesce(
            lead(snapshot_at) over (partition by repo_id order by snapshot_at),
            '9999-12-31'::timestamp_tz
        )                                                   as valid_to
    from versions
)

select
    {{ dbt_utils.generate_surrogate_key(['repo_id', 'valid_from']) }} as repo_key,
    repo_id,
    repo_name,
    owner_login,
    owner_type,
    primary_language,
    license_spdx_id,
    is_archived,
    is_fork,
    default_branch,
    valid_from,
    valid_to,
    valid_to = '9999-12-31'::timestamp_tz                   as is_current
from dated
