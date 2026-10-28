-- Reconciliation test: valid + rejected rows must add up to the de-duplicated
-- input. Catches a bad join or filter that silently drops data.

select source_month
from {{ ref('mart_data_quality') }}
where raw_rows <> duplicate_rows + valid_rows + rejected_rows
