-- One row per calendar day. Facts join here via date_key (YYYYMMDD).

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2008-01-01' as date)",
        end_date="cast('2028-01-01' as date)"
    ) }}
)

select
    to_number(to_char(date_day, 'YYYYMMDD'))    as date_key,
    date_day                                    as calendar_date,
    year(date_day)                              as year,
    quarter(date_day)                           as quarter,
    month(date_day)                             as month,
    monthname(date_day)                         as month_name,
    to_char(date_day, 'YYYY-MM')                as year_month,
    date_trunc('week', date_day)                as week_start_date,
    weekiso(date_day)                           as iso_week,
    dayofweekiso(date_day)                      as day_of_week,   -- 1 = Monday, 7 = Sunday
    dayname(date_day)                           as day_name,
    dayofweekiso(date_day) in (6, 7)            as is_weekend,
    date_day = last_day(date_day)               as is_month_end
from spine
