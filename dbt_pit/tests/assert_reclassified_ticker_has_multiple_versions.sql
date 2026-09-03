-- Unique to this dataset: every ticker named in the sourced seed table must
-- have at least two dimension rows. This is directly checkable against
-- sector_history because every event in it is a documented source, not a
-- derived business rule - if a reclassified ticker has only one version, the
-- SCD2 build process failed to apply its event, and that is a defect in the
-- pipeline rather than a modelling judgement call.

select
    s.ticker,
    count(d.ticker) as dimension_rows
from {{ source('bronze', 'sector_history') }} as s
-- Scoped to the analysable universe: a ticker delisted since 2018 (TWTR,
-- ATVI, TRIP, ETSY) has no dimension row by design - see
-- docs/sector_sources.md section 6.1 - and asserting >= 2 for it would fail
-- on a documented, intentional exclusion rather than a real defect.
join {{ source('silver_pipeline', 'ticker_universe') }} as u on u.ticker = s.ticker
left join {{ source('silver_pipeline', 'dim_sector_scd') }} as d on d.ticker = s.ticker
group by s.ticker
having count(d.ticker) < 2
