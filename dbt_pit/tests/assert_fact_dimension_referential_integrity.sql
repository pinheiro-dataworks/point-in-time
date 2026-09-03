-- Every (ticker, trade_date) in the fact table must resolve to EXACTLY ONE
-- dimension row under the point-in-time range join. Zero means the dimension
-- has a gap under that ticker; more than one means it has an overlap. Either
-- is a defect this test surfaces directly, independent of the two tests above
-- that check for the same defects from the dimension's own side.

select
    f.ticker,
    f.trade_date,
    count(d.ticker) as matching_dimension_rows
from {{ source('silver_pipeline', 'fact_returns') }} as f
left join {{ source('silver_pipeline', 'dim_sector_scd') }} as d
       on d.ticker = f.ticker
      and f.trade_date between d.valid_from
                            and coalesce(d.valid_to, date '9999-12-31')
group by f.ticker, f.trade_date
having count(d.ticker) != 1
