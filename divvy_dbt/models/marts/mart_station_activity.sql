-- Busiest docking stations by departures, split by rider type.

select
    start_station_id                                        as station_id,
    any_value(start_station_name)                           as station_name,
    count(*)                                                as departures,
    count(*) filter (where rider_type = 'member')           as member_departures,
    count(*) filter (where rider_type = 'casual')           as casual_departures,
    round(avg(duration_min), 1)                             as avg_duration_min
from {{ ref('fct_trips') }}
where start_station_id is not null
group by start_station_id
order by departures desc
