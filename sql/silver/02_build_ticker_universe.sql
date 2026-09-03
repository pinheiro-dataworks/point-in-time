-- ===========================================================================
-- 02_build_ticker_universe.sql — resolve the analysable ticker set
-- ===========================================================================
-- Joins the price corpus to the current-constituent snapshot, normalising the
-- one systematic difference between them (share-class punctuation) and
-- recording every ticker that still fails to match.
--
-- Depends on: bronze.daily_prices, bronze.sp500_current_snapshot
-- Produces:   silver.ticker_universe, silver.excluded_tickers
-- ===========================================================================

TRUNCATE TABLE silver.ticker_universe;
TRUNCATE TABLE silver.excluded_tickers;

-- ---------------------------------------------------------------------------
-- The universe: tickers with both a price series and a current sector.
-- ---------------------------------------------------------------------------
WITH price_coverage AS (
    -- One row per ticker describing the extent of its price history. Computed
    -- once here so downstream models never re-scan the 1.2M-row fact table
    -- just to ask "when does this ticker start?".
    SELECT
        ticker,
        MIN(trade_date) AS first_trade_date,
        MAX(trade_date) AS last_trade_date,
        COUNT(*)        AS trading_days
    FROM bronze.daily_prices
    GROUP BY ticker
),
snapshot_normalised AS (
    -- BRK.B (snapshot) and BRK-B (prices) are the same security. The dot is a
    -- source convention, not an identity difference, so it is normalised away.
    -- snapshot_ticker is carried through to keep the mapping reversible.
    SELECT
        REPLACE(ticker, '.', '-') AS ticker,
        ticker                    AS snapshot_ticker,
        security_name,
        gics_sector,
        gics_sub_industry
    FROM bronze.sp500_current_snapshot
)
INSERT INTO silver.ticker_universe (
    ticker, snapshot_ticker, security_name,
    current_gics_sector, current_sub_industry,
    first_trade_date, last_trade_date, trading_days
)
SELECT
    p.ticker,
    s.snapshot_ticker,
    s.security_name,
    s.gics_sector,
    s.gics_sub_industry,
    p.first_trade_date,
    p.last_trade_date,
    p.trading_days
FROM price_coverage p
JOIN snapshot_normalised s USING (ticker)
-- A ticker without a current sector cannot be joined naively OR correctly,
-- so it contributes nothing to the comparison this project makes.
WHERE s.gics_sector IS NOT NULL
  -- Deliberate hold-outs: price series backfilled across a corporate
  -- restructuring, or a current sector whose start date makes the
  -- "never changed" assumption provably false with no source to replace it.
  -- Listed in dbt_pit/seeds/excluded_entities.csv with a reason each.
  AND NOT EXISTS (
      SELECT 1 FROM bronze.excluded_entities e WHERE e.ticker = p.ticker
  );


-- ---------------------------------------------------------------------------
-- The exclusions: recorded, not discarded.
-- ---------------------------------------------------------------------------
-- An inner join silently drops non-matching rows. For a project whose entire
-- subject is data that goes quietly wrong, dropping rows without counting them
-- would be self-defeating. Both directions of the mismatch are stored.
-- ---------------------------------------------------------------------------
INSERT INTO silver.excluded_tickers (ticker, present_in, exclusion_reason)
SELECT
    s.ticker,
    'snapshot_only',
    'Listed as a current S&P 500 constituent but absent from the price corpus. '
    'The two sources were captured at different times, so recent index '
    'additions and post-capture ticker renames appear here.'
FROM bronze.sp500_current_snapshot s
WHERE NOT EXISTS (
    SELECT 1
    FROM silver.ticker_universe u
    WHERE u.snapshot_ticker = s.ticker
);

INSERT INTO silver.excluded_tickers (ticker, present_in, exclusion_reason)
SELECT
    DISTINCT p.ticker,
    'prices_only',
    'Has price history but no current GICS sector in the constituent snapshot. '
    'Typically a ticker removed from the index, or renamed, between the two '
    'source captures.'
FROM bronze.daily_prices p
WHERE NOT EXISTS (
    SELECT 1
    FROM silver.ticker_universe u
    WHERE u.ticker = p.ticker
)
AND NOT EXISTS (
    SELECT 1 FROM bronze.excluded_entities e WHERE e.ticker = p.ticker
);

-- Deliberate hold-outs are recorded under their own label so they are never
-- confused with source-mismatch casualties. These were excluded by decision,
-- not by an accident of joining.
INSERT INTO silver.excluded_tickers (ticker, present_in, exclusion_reason)
SELECT
    e.ticker,
    'held_out:' || e.exclusion_class,
    e.exclusion_reason
FROM bronze.excluded_entities e;

ANALYZE silver.ticker_universe;
ANALYZE silver.excluded_tickers;
