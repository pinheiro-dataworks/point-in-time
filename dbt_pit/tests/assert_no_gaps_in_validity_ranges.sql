-- Every ticker's validity chain must cover every TRADING day with no gap.
--
-- The naive version of this test checks calendar-day contiguity: valid_to +
-- 1 day == next valid_from. That is the wrong invariant for this dataset and
-- it fails loudly if you write it: both reclassification events took effect
-- after a Friday close (2018-09-21, 2023-03-17) with the new version starting
-- the following Monday (2018-09-24, 2023-03-20). valid_to + 1 day lands on a
-- Saturday, which is never anyone's valid_from, so a strict calendar-adjacency
-- check flags all 31 reclassified tickers as "gapped" even though nothing is
-- actually missing - there were no trading days in that gap to miss. The same
-- mechanic is walked through in sql/analyses/recursive_sector_chain.sql.
--
-- The invariant that actually matters: no OBSERVED trading day falls strictly
-- between one version's valid_to and the next version's valid_from. That is
-- exactly what this checks, against the real trading calendar in
-- silver.fact_returns rather than against calendar arithmetic.

with ordered as (

    select
        ticker,
        valid_from,
        valid_to,
        row_number() over (partition by ticker order by valid_from) as rn
    from {{ source('silver_pipeline', 'dim_sector_scd') }}
    where valid_to is not null  -- only closed versions have a successor to check

),

chain_boundaries as (

    select
        a.ticker,
        a.valid_to    as gap_starts_after,
        b.valid_from  as gap_ends_before
    from ordered as a
    join ordered as b
      on a.ticker = b.ticker
     and b.rn = a.rn + 1

)

select
    c.ticker,
    c.gap_starts_after,
    c.gap_ends_before,
    f.trade_date as orphaned_trading_day
from chain_boundaries as c
join {{ source('silver_pipeline', 'fact_returns') }} as f
  on f.ticker = c.ticker
 and f.trade_date > c.gap_starts_after
 and f.trade_date < c.gap_ends_before
