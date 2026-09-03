-- Every ticker in the dimension must have exactly one is_current = TRUE row.
-- Zero would mean the ticker has no present-day sector to naive-join against;
-- more than one would make gold.fact_returns_pit's naive join non-deterministic.

select
    ticker,
    count(*) as current_row_count
from {{ source('silver_pipeline', 'dim_sector_scd') }}
where is_current
group by ticker
having count(*) != 1
