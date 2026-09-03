-- ===========================================================================
-- 02_build_fact_returns_pit.sql - the range join
-- ===========================================================================
-- The technical core of the project. Every return observation is joined to the
-- sector dimension TWICE:
--
--   d_pit - by DATE RANGE, resolving the sector that was valid on the trade
--           date. This is the correct join.
--   d_now - by is_current, resolving the sector the ticker carries today and
--           applying it retroactively to every historical row. This is the
--           join almost every sector report actually performs.
--
-- Both joins are INNER, which is a deliberate assertion rather than a
-- convenience. The dimension's earliest version starts at the 1900-01-01
-- sentinel and the validity chain has no gaps, so every fact row MUST resolve
-- to exactly one dimension row. If that stops being true the row count drops,
-- and the test in dbt_pit/tests/ fails. An outer join would hide exactly the
-- defect this project is about.
--
-- Depends on: silver.fact_returns, silver.dim_sector_scd
-- Produces:   gold.fact_returns_pit
-- ===========================================================================

TRUNCATE TABLE gold.fact_returns_pit;

INSERT INTO gold.fact_returns_pit (
    ticker, trade_date, daily_return, log_return,
    sector_key, sector_at_trade_date, sector_today, is_misattributed
)
SELECT
    f.ticker,
    f.trade_date,
    f.daily_return,
    f.log_return,
    d_pit.sector_key,
    d_pit.gics_sector AS sector_at_trade_date,
    d_now.gics_sector AS sector_today,
    (d_pit.gics_sector <> d_now.gics_sector) AS is_misattributed
FROM silver.fact_returns AS f

-- --- the point-in-time join ------------------------------------------------
-- BETWEEN is inclusive at both ends, which is what the dimension's closed
-- interval semantics require: valid_to holds the LAST day the version was in
-- force, not the first day it was not.
--
-- COALESCE on valid_to turns the open-ended current row into a bounded one.
-- Using a far-future sentinel rather than `OR valid_to IS NULL` keeps the
-- predicate sargable, so the composite index on (ticker, valid_from, valid_to)
-- can actually be used - see docs/performance.md.
JOIN silver.dim_sector_scd AS d_pit
  ON  d_pit.ticker = f.ticker
  AND f.trade_date BETWEEN d_pit.valid_from
                       AND COALESCE(d_pit.valid_to, DATE '9999-12-31')

-- --- the naive join --------------------------------------------------------
-- No date predicate at all. That absence IS the bug: the ticker's present-day
-- sector is attached to observations from years earlier.
JOIN silver.dim_sector_scd AS d_now
  ON  d_now.ticker = f.ticker
  AND d_now.is_current

-- A ticker's first observed day has no previous close and therefore no return.
-- Excluding it here keeps NULLs out of every downstream average.
WHERE f.daily_return IS NOT NULL;

ANALYZE gold.fact_returns_pit;
