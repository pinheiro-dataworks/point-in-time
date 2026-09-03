-- ===========================================================================
-- 03_build_sector_returns.sql - equal-weighted sector indices, both bases
-- ===========================================================================
-- Aggregates the twice-joined fact into a sector return series, once per join
-- basis. The two series are produced by the SAME arithmetic over the SAME
-- rows; they differ only in which column supplies the sector label.
--
-- Method: equal-weighted, daily-rebalanced. Each trading day, the sector
-- return is the mean of its constituents' daily returns; the index compounds
-- those means. Equal weighting is forced by the data - the corpus has no
-- shares-outstanding or market-cap column, so cap weighting is not available.
-- Stated explicitly here and in the README rather than left for a reader to
-- infer.
--
-- Depends on: gold.fact_returns_pit, silver.analysis_window
-- Produces:   gold.sector_daily_returns, gold.sector_cumulative_returns
-- ===========================================================================

TRUNCATE TABLE gold.sector_daily_returns;
TRUNCATE TABLE gold.sector_cumulative_returns;

-- ---------------------------------------------------------------------------
-- Daily equal-weighted sector return, both bases in one pass
-- ---------------------------------------------------------------------------
INSERT INTO gold.sector_daily_returns (join_basis, gics_sector, trade_date, constituent_count, mean_return)
WITH windowed AS (
    SELECT f.*
    FROM gold.fact_returns_pit AS f
    CROSS JOIN silver.analysis_window AS w
    WHERE f.trade_date BETWEEN w.start_date AND w.end_date
),
-- UNPIVOT the two sector labels into rows so that one GROUP BY serves both
-- bases. Writing it as two near-identical aggregate queries would invite the
-- two definitions to drift apart under maintenance.
labelled AS (
    SELECT 'point_in_time' AS join_basis, sector_at_trade_date AS gics_sector, trade_date, daily_return
    FROM windowed
    UNION ALL
    SELECT 'naive'         AS join_basis, sector_today         AS gics_sector, trade_date, daily_return
    FROM windowed
)
SELECT
    join_basis,
    gics_sector,
    trade_date,
    COUNT(*)            AS constituent_count,
    AVG(daily_return)   AS mean_return
FROM labelled
GROUP BY join_basis, gics_sector, trade_date;


-- ---------------------------------------------------------------------------
-- Compound the daily means into a cumulative index
-- ---------------------------------------------------------------------------
-- Compounding is a running PRODUCT, and SQL has no product aggregate. The
-- standard identity converts it into a running SUM in log space:
--
--     PROD(1 + r_i)  =  EXP( SUM( LN(1 + r_i) ) )
--
-- which a window function computes in a single ordered pass. Doing it with a
-- self-join or a recursive CTE would be O(n^2) over ~1.19M rows.
--
-- GREATEST(..., -0.9999) guards the logarithm: LN is undefined at zero and
-- negative, and a daily mean return of exactly -100% would abort the query.
-- No such value occurs in this corpus - an equal-weighted mean across dozens
-- of constituents cannot reach -100% - so the guard never fires here. It is
-- present so the model stays total for any future input rather than being
-- correct only by luck.
-- ---------------------------------------------------------------------------
INSERT INTO gold.sector_cumulative_returns (
    join_basis, gics_sector, trade_date, mean_return, cumulative_index, cumulative_return
)
SELECT
    join_basis,
    gics_sector,
    trade_date,
    mean_return,
    EXP(SUM(LN(1 + GREATEST(mean_return, -0.9999))) OVER (
        PARTITION BY join_basis, gics_sector
        ORDER BY     trade_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )) AS cumulative_index,
    EXP(SUM(LN(1 + GREATEST(mean_return, -0.9999))) OVER (
        PARTITION BY join_basis, gics_sector
        ORDER BY     trade_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )) - 1 AS cumulative_return
FROM gold.sector_daily_returns;

ANALYZE gold.sector_daily_returns;
ANALYZE gold.sector_cumulative_returns;
