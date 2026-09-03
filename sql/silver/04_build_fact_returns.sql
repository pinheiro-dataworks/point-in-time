-- ===========================================================================
-- 04_build_fact_returns.sql — daily returns via window functions
-- ===========================================================================
-- Converts a price level series into a return series. The whole calculation is
-- one LAG partitioned by ticker and ordered by trade date — which is exactly
-- why window functions exist, and why doing this with a self-join would be
-- both slower and harder to read.
--
-- One correctness point worth stating plainly: LAG is ordered by trade_date
-- within each ticker, so "previous close" means the previous *observed
-- trading day*, not "yesterday". Weekends, holidays and trading halts are
-- therefore handled implicitly and correctly — a date-arithmetic version
-- (trade_date - 1) would produce NULLs every Monday.
--
-- Depends on: bronze.daily_prices, silver.ticker_universe
-- Produces:   silver.fact_returns
-- ===========================================================================

TRUNCATE TABLE silver.fact_returns;

INSERT INTO silver.fact_returns (
    ticker, trade_date, close_price, prev_close, daily_return, log_return, volume
)
WITH priced AS (
    SELECT
        p.ticker,
        p.trade_date,
        p.close_price,
        p.volume,
        LAG(p.close_price) OVER (
            PARTITION BY p.ticker
            ORDER BY     p.trade_date
        ) AS prev_close
    FROM bronze.daily_prices AS p
    -- Restricting to the analysable universe here rather than downstream keeps
    -- the fact table and the dimension on the same ticker set, which is what
    -- makes the Gold-layer referential-integrity test meaningful.
    JOIN silver.ticker_universe AS u ON u.ticker = p.ticker
    WHERE p.close_price IS NOT NULL
)
SELECT
    ticker,
    trade_date,
    close_price,
    prev_close,
    -- NULLIF guards against a zero previous close. A zero price is not
    -- meaningful for an equity and would raise a division error; producing
    -- NULL instead keeps the row and marks the return as unknown, which is
    -- the honest representation.
    close_price / NULLIF(prev_close, 0) - 1                 AS daily_return,
    LN(close_price / NULLIF(prev_close, 0))                 AS log_return,
    volume
FROM priced;

ANALYZE silver.fact_returns;
