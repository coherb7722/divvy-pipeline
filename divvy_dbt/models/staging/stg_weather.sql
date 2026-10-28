select
    date                                as weather_date,
    temp_max_f,
    temp_min_f,
    round((temp_max_f + temp_min_f) / 2, 1) as temp_avg_f,
    precipitation_in,
    wind_max_mph,
    precipitation_in >= 0.1             as is_rainy_day
from {{ source('raw', 'weather_daily') }}
