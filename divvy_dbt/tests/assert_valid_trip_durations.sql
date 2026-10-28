-- Business-rule test: every ride that reaches the fact table must last
-- between 1 minute and 24 hours. Returns the offending rows; zero rows = pass.

select ride_id, duration_min
from {{ ref('fct_trips') }}
where duration_min < 1 or duration_min > 24 * 60
