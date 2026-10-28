-- Apply data-quality rules. Instead of silently deleting bad rows, every row
-- gets a flag and a reason. Valid rows flow to the marts; invalid rows are
-- counted in mart_data_quality so nothing disappears without a trace.

with trips as (
    select
        *,
        date_diff('second', started_at, ended_at) / 60.0 as duration_min
    from {{ ref('stg_trips') }}
)

select
    *,
    case
        when started_at is null or ended_at is null then 'bad_timestamp'
        when ended_at <= started_at         then 'ended_before_start'
        when duration_min < 1                then 'under_1_minute'
        when duration_min > 24 * 60          then 'over_24_hours'
        when rider_type not in ('member', 'casual') then 'unknown_rider_type'
        else null
    end as invalid_reason,
    invalid_reason is null as is_valid
from trips
