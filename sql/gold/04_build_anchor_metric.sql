-- ===========================================================================
-- 04_build_anchor_metric.sql - the headline result
-- ===========================================================================
-- Reduces the pipeline to one row per sector: what does the naive join cost,
-- in percentage points, and how much history does it move?
--
-- WHY THE COMPARISON IS REBASED
-- -----------------------------
-- A first pass at this compared each sector's naive total return against its
-- point-in-time total return over the full analysis window. That comparison is
-- invalid, and the reason is worth stating because it is the same species of
-- error the project is about.
--
-- Communication Services did not exist before 2018-09-24. Under the
-- point-in-time basis its series therefore *starts* on that date, and its
-- "total return" covers 7.2 years. Under the naive basis every current
-- Communication Services constituent is back-labelled to 2016-01-01, so its
-- series covers 10 years. Subtracting one from the other yields a large number
-- that is mostly calendar length, not join error - measuring two different
-- periods and attributing the gap to the wrong cause.
--
-- The fix: compound both bases over [comparison_start, analysis_end], where
-- comparison_start is the first date on which BOTH series exist. Identical
-- dates on both sides, so the residual is attributable to membership alone.
--
-- The full-window naive figure is not discarded - it is what a naive report
-- would actually publish, and the gap between it and reality is the second
-- finding. It is stored in its own column so the two effects stay separable.
--
-- Depends on: gold.sector_daily_returns, gold.fact_returns_pit,
--             silver.dim_sector_scd, silver.analysis_window
-- Produces:   gold.anchor_metric
-- ===========================================================================

TRUNCATE TABLE gold.anchor_metric;

INSERT INTO gold.anchor_metric (
    gics_sector, analysis_start, analysis_end, comparison_start,
    naive_cumulative_return, pit_cumulative_return,
    difference_pp, abs_difference_pp, naive_full_window_return,
    exists_in_naive_basis, exists_in_pit_basis,
    reclassified_tickers, misattributed_observations,
    sector_existed_from, trading_days_in_window,
    trading_days_sector_absent, pct_period_sector_absent
)
WITH win AS (
    SELECT start_date, end_date FROM silver.analysis_window
),

-- --- where each series begins ---------------------------------------------
series_bounds AS (
    SELECT join_basis, gics_sector, MIN(trade_date) AS first_date
    FROM gold.sector_daily_returns
    GROUP BY join_basis, gics_sector
),

-- The later of the two starts. MAX over the bases gives the first date on
-- which both series are simultaneously defined.
comparison_window AS (
    SELECT
        gics_sector,
        MAX(first_date)  AS comparison_start,
        COUNT(*)         AS bases_present
    FROM series_bounds
    GROUP BY gics_sector
),

-- --- like-for-like cumulative return, per basis ---------------------------
-- Recompounded from comparison_start rather than sliced out of the running
-- index, so no rebasing arithmetic is needed and the result is exact.
comparable AS (
    SELECT
        d.join_basis,
        d.gics_sector,
        EXP(SUM(LN(1 + GREATEST(d.mean_return, -0.9999)))) - 1 AS cumulative_return
    FROM gold.sector_daily_returns AS d
    JOIN comparison_window AS c ON c.gics_sector = d.gics_sector
    WHERE d.trade_date >= c.comparison_start
    GROUP BY d.join_basis, d.gics_sector
),

-- --- what a naive report actually publishes -------------------------------
full_window_naive AS (
    SELECT
        gics_sector,
        EXP(SUM(LN(1 + GREATEST(mean_return, -0.9999)))) - 1 AS cumulative_return
    FROM gold.sector_daily_returns
    WHERE join_basis = 'naive'
    GROUP BY gics_sector
),

-- Pivot the two bases side by side. FULL OUTER, not INNER: a sector present in
-- only one basis must survive, because its absence from the other IS a finding
-- (Telecommunication Services has no naive series at all - it is nobody's
-- current sector, so a naive report erases it from history entirely).
paired AS (
    SELECT
        COALESCE(p.gics_sector, n.gics_sector) AS gics_sector,
        n.cumulative_return                    AS naive_cumulative_return,
        p.cumulative_return                    AS pit_cumulative_return,
        (n.gics_sector IS NOT NULL)            AS exists_in_naive_basis,
        (p.gics_sector IS NOT NULL)            AS exists_in_pit_basis
    FROM      (SELECT * FROM comparable WHERE join_basis = 'point_in_time') AS p
    FULL JOIN (SELECT * FROM comparable WHERE join_basis = 'naive')         AS n
           ON n.gics_sector = p.gics_sector
),

-- --- how much history the naive join moves --------------------------------
-- A row is relevant to sector S if S is either where the observation actually
-- belonged, or where the naive join files it. Both directions matter: one is
-- return the sector should have been credited with, the other is return it is
-- wrongly credited with.
misattributed_rows AS (
    SELECT f.ticker, f.sector_at_trade_date, f.sector_today
    FROM gold.fact_returns_pit AS f
    CROSS JOIN win AS w
    WHERE f.is_misattributed
      AND f.trade_date BETWEEN w.start_date AND w.end_date
),
misattribution AS (
    SELECT
        s.gics_sector,
        COUNT(*)                 AS misattributed_observations,
        COUNT(DISTINCT s.ticker) AS reclassified_tickers
    FROM (
        SELECT ticker, sector_at_trade_date AS gics_sector FROM misattributed_rows
        UNION ALL
        SELECT ticker, sector_today         AS gics_sector FROM misattributed_rows
    ) AS s
    GROUP BY s.gics_sector
),

-- --- when each sector came into existence ---------------------------------
-- The earliest valid_from across every dimension row carrying the sector. The
-- 1900-01-01 sentinel means the sector was in force for the entire window;
-- anything later means it was created partway through.
sector_birth AS (
    SELECT gics_sector, MIN(valid_from) AS sector_existed_from
    FROM silver.dim_sector_scd
    GROUP BY gics_sector
),

-- Trading days, not calendar days: weekends and holidays carry no return and
-- would dilute the percentage.
trading_calendar AS (
    SELECT COUNT(DISTINCT f.trade_date) AS trading_days_in_window
    FROM gold.fact_returns_pit AS f
    CROSS JOIN win AS w
    WHERE f.trade_date BETWEEN w.start_date AND w.end_date
),

absent_days AS (
    SELECT
        b.gics_sector,
        COUNT(DISTINCT f.trade_date) AS trading_days_sector_absent
    FROM sector_birth AS b
    CROSS JOIN win AS w
    LEFT JOIN gold.fact_returns_pit AS f
           ON f.trade_date BETWEEN w.start_date AND w.end_date
          AND f.trade_date < b.sector_existed_from
    GROUP BY b.gics_sector
)

SELECT
    p.gics_sector,
    w.start_date,
    w.end_date,
    cw.comparison_start,
    p.naive_cumulative_return * 100,
    p.pit_cumulative_return   * 100,
    (p.naive_cumulative_return - p.pit_cumulative_return) * 100      AS difference_pp,
    ABS((p.naive_cumulative_return - p.pit_cumulative_return) * 100) AS abs_difference_pp,
    fw.cumulative_return * 100                                       AS naive_full_window_return,
    p.exists_in_naive_basis,
    p.exists_in_pit_basis,
    COALESCE(m.reclassified_tickers, 0),
    COALESCE(m.misattributed_observations, 0),
    b.sector_existed_from,
    c.trading_days_in_window,
    COALESCE(a.trading_days_sector_absent, 0),
    ROUND(
        100.0 * COALESCE(a.trading_days_sector_absent, 0) / NULLIF(c.trading_days_in_window, 0),
        4
    )::DOUBLE PRECISION
FROM paired AS p
CROSS JOIN win AS w
CROSS JOIN trading_calendar AS c
LEFT JOIN comparison_window AS cw ON cw.gics_sector = p.gics_sector
LEFT JOIN full_window_naive AS fw ON fw.gics_sector = p.gics_sector
LEFT JOIN misattribution    AS m  ON m.gics_sector  = p.gics_sector
LEFT JOIN sector_birth      AS b  ON b.gics_sector  = p.gics_sector
LEFT JOIN absent_days       AS a  ON a.gics_sector  = p.gics_sector;

ANALYZE gold.anchor_metric;
