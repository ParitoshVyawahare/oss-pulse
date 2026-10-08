-- Singular test: in an SCD Type 2 dimension every repo must have exactly ONE current version.
-- Returns repos with zero or several current rows.

select
    repo_id,
    count_if(is_current) as current_versions
from {{ ref('dim_repo') }}
group by repo_id
having count_if(is_current) <> 1
