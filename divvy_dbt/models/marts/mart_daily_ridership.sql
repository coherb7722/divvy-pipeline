-- One row per day: ridership by rider type next to that day's weather.
-- This is the table the dashboard answers "does weather change ridership?" from.

select
    w.weather_date                                          as ride_date,
    dayname(w.weather_date)                                 as day_of_week,
    isodow(w.weather_date) >= 6                             as is_weekend,
    count(f.ride_id)                                        as total_rides,
    count(f.ride_id) filter (where f.rider_type = 'member') as member_rides,
    count(f.ride_id) filter (where f.rider_type = 'casual') as casual_rides,
    round(median(f.duration_min), 1)                        as median_duration_min,
    w.temp_max_f,
    w.temp_avg_f,
    w.precipitation_in,
    w.is_rainy_day
from {{ ref('stg_weather') }} w
left join {{ ref('fct_trips') }} f
    on f.ride_date = w.weather_date
-- Only days inside the loaded months. The extra boundary day (e.g. May 31)
-- holds just the few rides that crossed midnight, so it would look like a
-- near-empty day on the chart.
where strftime(w.weather_date, '%Y-%m') in (
    select distinct _source_month from {{ source('raw', 'trips') }}
)
group by all
order by ride_date
