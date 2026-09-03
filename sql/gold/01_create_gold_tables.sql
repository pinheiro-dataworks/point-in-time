-- ===========================================================================
-- 01_create_gold_tables.sql - business-facing model
-- ===========================================================================
-- Gold answers one question in two different ways and reports the gap:
--
--   "What was sector X's return over period P?"
--
--   point_in_time - each trade joined to the sector valid ON that trade date
--   naive         - each trade joined to the sector the ticker has TODAY
--
-- Same prices, same tickers, same arithmetic. The only difference is the join.
-- ===========================================================================

-- The reporting period is defined once, in silver.analysis_window, and read
-- from there by every Gold model.

-- ---------------------------------------------------------------------------
-- gold.fact_returns_pit - the range-joined fact
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS gold.fact_returns_pit CASCADE;
CREATE TABLE gold.fact_returns_pit (
    ticker               TEXT   NOT NULL,
    trade_date           DATE   NOT NULL,
    daily_return         DOUBLE PRECISION,
    log_return           DOUBLE PRECISION,
    sector_key           BIGINT NOT NULL,
    sector_at_trade_date TEXT   NOT NULL,
    sector_today         TEXT   NOT NULL,
    is_misattributed     BOOLEAN NOT NULL,
    CONSTRAINT pk_fact_returns_pit PRIMARY KEY (ticker, trade_date)
);

COMMENT ON TABLE gold.fact_returns_pit IS
    'Every return observation carrying BOTH sector labels: the one valid on '
    'the trade date, and the one the ticker carries today. Rows where they '
    'differ are exactly the rows a naive report gets wrong.';

COMMENT ON COLUMN gold.fact_returns_pit.sector_key IS
    'Surrogate key of the dimension version that was valid on trade_date. '
    'Resolved by range join, not by is_current.';

COMMENT ON COLUMN gold.fact_returns_pit.is_misattributed IS
    'TRUE when sector_at_trade_date <> sector_today, i.e. a naive join files '
    'this observation under the wrong sector. Counting these is the most '
    'direct statement of the problem''s size.';


-- ---------------------------------------------------------------------------
-- gold.sector_daily_returns - equal-weighted sector index, both bases
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS gold.sector_daily_returns CASCADE;
CREATE TABLE gold.sector_daily_returns (
    join_basis       TEXT   NOT NULL,
    gics_sector      TEXT   NOT NULL,
    trade_date       DATE   NOT NULL,
    constituent_count INTEGER NOT NULL,
    mean_return      DOUBLE PRECISION NOT NULL,
    CONSTRAINT pk_sector_daily_returns PRIMARY KEY (join_basis, gics_sector, trade_date),
    CONSTRAINT ck_join_basis CHECK (join_basis IN ('point_in_time', 'naive'))
);

COMMENT ON TABLE gold.sector_daily_returns IS
    'Equal-weighted, daily-rebalanced sector return. One row per sector per '
    'trading day per join basis.';

COMMENT ON COLUMN gold.sector_daily_returns.mean_return IS
    'Equal-weighted mean of constituent daily returns. Equal weighting is a '
    'deliberate constraint, not a preference: the price corpus carries no '
    'shares-outstanding or market-cap data, so a cap-weighted index cannot be '
    'computed from it honestly. Stated in the README rather than implied.';

COMMENT ON COLUMN gold.sector_daily_returns.constituent_count IS
    'Tickers contributing on this date. Under the point_in_time basis this '
    'changes on reclassification dates; under the naive basis it never does - '
    'which is itself the visible symptom of the bug.';


-- ---------------------------------------------------------------------------
-- gold.sector_cumulative_returns - the series the dashboard plots
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS gold.sector_cumulative_returns CASCADE;
CREATE TABLE gold.sector_cumulative_returns (
    join_basis        TEXT   NOT NULL,
    gics_sector       TEXT   NOT NULL,
    trade_date        DATE   NOT NULL,
    mean_return       DOUBLE PRECISION NOT NULL,
    cumulative_index  DOUBLE PRECISION NOT NULL,
    cumulative_return DOUBLE PRECISION NOT NULL,
    CONSTRAINT pk_sector_cumulative_returns PRIMARY KEY (join_basis, gics_sector, trade_date),
    CONSTRAINT ck_cum_join_basis CHECK (join_basis IN ('point_in_time', 'naive'))
);

COMMENT ON COLUMN gold.sector_cumulative_returns.cumulative_index IS
    'Growth of 1.00 invested at the start of the analysis window, compounded '
    'through the equal-weighted daily returns.';

COMMENT ON COLUMN gold.sector_cumulative_returns.cumulative_return IS
    'cumulative_index - 1, expressed as a decimal fraction.';


-- ---------------------------------------------------------------------------
-- gold.anchor_metric - the headline result
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS gold.anchor_metric CASCADE;
CREATE TABLE gold.anchor_metric (
    gics_sector                 TEXT NOT NULL,
    analysis_start              DATE NOT NULL,
    analysis_end                DATE NOT NULL,

    -- --- the like-for-like comparison -------------------------------------
    -- Both figures are compounded over [comparison_start, analysis_end], the
    -- period where BOTH bases have data. See the header of
    -- 04_build_anchor_metric.sql for why this rebasing is mandatory.
    comparison_start            DATE,
    naive_cumulative_return     DOUBLE PRECISION,
    pit_cumulative_return       DOUBLE PRECISION,
    difference_pp               DOUBLE PRECISION,
    abs_difference_pp           DOUBLE PRECISION,

    -- --- the full-window naive figure -------------------------------------
    -- What a naive report would actually publish: compounded from
    -- analysis_start regardless of whether the sector existed then. Kept
    -- separate from the comparison above so the two distinct errors - wrong
    -- membership, and returns predating the sector - are never conflated.
    naive_full_window_return    DOUBLE PRECISION,

    exists_in_naive_basis       BOOLEAN NOT NULL,
    exists_in_pit_basis         BOOLEAN NOT NULL,
    reclassified_tickers        INTEGER NOT NULL,
    misattributed_observations  BIGINT  NOT NULL,
    sector_existed_from         DATE,
    trading_days_in_window      INTEGER NOT NULL,
    trading_days_sector_absent  INTEGER NOT NULL,
    pct_period_sector_absent    DOUBLE PRECISION NOT NULL,
    CONSTRAINT pk_anchor_metric PRIMARY KEY (gics_sector)
);

COMMENT ON TABLE gold.anchor_metric IS
    'One row per sector quantifying the cost of the naive join. Every figure '
    'is computed from the warehouse - none is estimated or hand-entered.';

COMMENT ON COLUMN gold.anchor_metric.comparison_start IS
    'First date on which both the naive and the point-in-time series exist. '
    'For every sector that predates the analysis window this equals '
    'analysis_start; for Communication Services it is 2018-09-24, the day the '
    'sector was created.';

COMMENT ON COLUMN gold.anchor_metric.difference_pp IS
    'naive_cumulative_return - pit_cumulative_return over the common period, '
    'in percentage points. Positive means the naive join OVERSTATES the '
    'sector''s return. Because both sides span identical dates, this isolates '
    'the join error with no calendar effect mixed in.';

COMMENT ON COLUMN gold.anchor_metric.naive_full_window_return IS
    'Naive return compounded from analysis_start. For Communication Services '
    'this covers 2.7 years during which the sector did not exist - the figure '
    'a naive report publishes, and one that never existed on any given day.';

COMMENT ON COLUMN gold.anchor_metric.pct_period_sector_absent IS
    'Share of the analysis window during which this sector did not yet exist '
    'under GICS. Non-zero only for Communication Services, created 2018-09-24. '
    'A naive report attributes returns to it for this entire stretch.';
