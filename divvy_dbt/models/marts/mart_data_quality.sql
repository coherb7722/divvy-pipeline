-- Data-quality report per source month: how many rows came in, how many
-- were duplicates, and why rows were rejected. Shown on the dashboard.

with raw_counts as (
    select _source_month, count(*) as raw_rows
    from {{ source('raw', 'trips') }}
    group by 1
),

validated as (
    select
        _source_month,
        count(*)                                                    as deduped_rows,
        count(*) filter (where is_valid)                            as valid_rows,
        count(*) filter (where invalid_reason = 'bad_timestamp')    as bad_timestamp,
        count(*) filter (where invalid_reason = 'ended_before_start') as ended_before_start,
        count(*) filter (where invalid_reason = 'under_1_minute')   as under_1_minute,
        count(*) filter (where invalid_reason = 'over_24_hours')    as over_24_hours,
        count(*) filter (where invalid_reason = 'unknown_rider_type') as unknown_rider_type,
        count(*) filter (where start_station_id is null)            as missing_start_station
    from {{ ref('int_trips_validated') }}
    group by 1
)

select
    r._source_month                                     as source_month,
    r.raw_rows,
    r.raw_rows - v.deduped_rows                         as duplicate_rows,
    v.valid_rows,
    v.deduped_rows - v.valid_rows                       as rejected_rows,
    round(100.0 * v.valid_rows / r.raw_rows, 2)         as pct_valid,
    v.bad_timestamp,
    v.ended_before_start,
    v.under_1_minute,
    v.over_24_hours,
    v.unknown_rider_type,
    v.missing_start_station
from raw_counts r
join validated v using (_source_month)
order by source_month
