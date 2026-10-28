-- Fact table: one row per valid ride, enriched with the weather that day.

select
    t.ride_id,
    t.rideable_type,
    t.rider_type,
    t.started_at,
    t.ended_at,
    cast(t.started_at as date)              as ride_date,
    hour(t.started_at)                      as start_hour,
    dayname(t.started_at)                   as day_of_week,
    isodow(t.started_at) >= 6               as is_weekend,
    round(t.duration_min, 1)                as duration_min,
    t.start_station_id,
    t.start_station_name,
    t.end_station_id,
    t.end_station_name,
    t.start_station_id is null              as is_dockless_start,
    w.temp_max_f,
    w.precipitation_in,
    w.is_rainy_day
from {{ ref('int_trips_validated') }} t
left join {{ ref('stg_weather') }} w
    on cast(t.started_at as date) = w.weather_date
where t.is_valid
