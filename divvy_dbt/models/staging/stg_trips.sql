-- Clean and type the raw trips. No business rules yet, just:
--   * cast text to proper types
--   * standardise names
--   * remove exact duplicate ride_ids that the source sometimes publishes

with source as (
    select * from {{ source('raw', 'trips') }}
),

typed as (
    select
        ride_id,
        rideable_type,
        -- try_cast: an unparseable timestamp becomes null and is flagged
        -- downstream, instead of crashing the whole build
        try_cast(started_at as timestamp)      as started_at,
        try_cast(ended_at   as timestamp)      as ended_at,
        nullif(trim(start_station_name), '')   as start_station_name,
        nullif(trim(start_station_id), '')     as start_station_id,
        nullif(trim(end_station_name), '')     as end_station_name,
        nullif(trim(end_station_id), '')       as end_station_id,
        start_lat, start_lng, end_lat, end_lng,
        member_casual                          as rider_type,
        _source_month,
        _loaded_at
    from source
),

deduped as (
    select *,
        row_number() over (partition by ride_id order by _loaded_at desc) as _row_num
    from typed
)

select * exclude (_row_num)
from deduped
where _row_num = 1
