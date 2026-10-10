-- Daily calendar for MetricFlow. Reuses dim_date so the project has ONE calendar.
select calendar_date as date_day
from {{ ref('dim_date') }}
