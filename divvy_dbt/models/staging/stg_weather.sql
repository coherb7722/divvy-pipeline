-- Weather is fetched with one extra day before each month (see extract.py),
-- so boundary days can arrive twice. Keep the most recently loaded copy.

select
    date                                as weather_date,
    temp_max_f,
    temp_min_f,
    round((temp_max_f + temp_min_f) / 2, 1) as temp_avg_f,
    precipitation_in,
    wind_max_mph,
    precipitation_in >= 0.1             as is_rainy_day
from {{ source('raw', 'weather_daily') }}
qualify row_number() over (partition by date order by _loaded_at desc) = 1
