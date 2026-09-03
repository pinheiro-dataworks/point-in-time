-- A singular test PASSES when it returns zero rows. Every row returned here
-- is a ticker with two dimension versions whose date ranges overlap - a
-- corruption that would make the point-in-time join in gold.fact_returns_pit
-- ambiguous (which version applies to that trade date?).

select
    a.ticker,
    a.valid_from  as version_a_from,
    a.valid_to    as version_a_to,
    b.valid_from  as version_b_from,
    b.valid_to    as version_b_to
from {{ source('silver_pipeline', 'dim_sector_scd') }} as a
join {{ source('silver_pipeline', 'dim_sector_scd') }} as b
  on  a.ticker = b.ticker
  and a.sector_key < b.sector_key
  and a.valid_from < b.valid_from
where a.valid_to is null or a.valid_to >= b.valid_from
