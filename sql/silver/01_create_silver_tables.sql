-- ===========================================================================
-- 01_create_silver_tables.sql — conformed model
-- ===========================================================================
-- Silver is where assertions live. Bronze records what the sources said;
-- Silver states what must be true, and the constraints here are the first
-- line of that defence (dbt tests are the second).
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- silver.analysis_window — the reporting period, as data
-- ---------------------------------------------------------------------------
-- The window lives in a table rather than being interpolated into each query
-- as a string. Two reasons: the SQL files stay executable by hand in psql with
-- no templating step, and every model provably shares one definition of the
-- period instead of drifting apart. Populated from PIT_ANALYSIS_START /
-- PIT_ANALYSIS_END by pit_lab.build.
--
-- It sits in Silver rather than Gold because Silver needs it too: the
-- sector-existence invariant is only meaningful when scoped to the window.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.analysis_window CASCADE;
CREATE TABLE silver.analysis_window (
    singleton   BOOLEAN PRIMARY KEY DEFAULT TRUE,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    CONSTRAINT ck_single_row   CHECK (singleton),
    CONSTRAINT ck_window_order CHECK (end_date > start_date)
);

COMMENT ON TABLE silver.analysis_window IS
    'Single-row configuration table holding the reporting period. The '
    'singleton CHECK makes a second row impossible, so no query needs to '
    'defend against picking the wrong window.';


-- ---------------------------------------------------------------------------
-- silver.ticker_universe — the analysable set
-- ---------------------------------------------------------------------------
-- A ticker is analysable only if it has BOTH price history and a current GICS
-- classification. The two sources disagree at the edges, for three distinct
-- reasons, and conflating them would be a mistake:
--
--   1. Punctuation convention. The constituent snapshot writes share classes
--      with a dot (BRK.B, BF.B); the price export uses a hyphen (BRK-B, BF-B).
--      Same security, different string. Normalised, not dropped.
--   2. Timing. The two sources were captured weeks apart, so recent index
--      additions appear in one and not the other.
--   3. Ticker renames. A security can change its ticker while remaining the
--      same company; each source caught a different side of the rename.
--
-- Only (1) is mechanically recoverable. (2) and (3) are genuine gaps and the
-- rows are excluded rather than guessed at - see silver.excluded_tickers,
-- which records them so the exclusion is auditable instead of invisible.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.ticker_universe CASCADE;
CREATE TABLE silver.ticker_universe (
    ticker              TEXT NOT NULL,
    snapshot_ticker     TEXT NOT NULL,
    security_name       TEXT,
    current_gics_sector TEXT NOT NULL,
    current_sub_industry TEXT,
    first_trade_date    DATE NOT NULL,
    last_trade_date     DATE NOT NULL,
    trading_days        INTEGER NOT NULL,
    CONSTRAINT pk_ticker_universe PRIMARY KEY (ticker)
);

COMMENT ON TABLE silver.ticker_universe IS
    'Tickers with both price history and a current GICS sector. The analysis '
    'universe for every downstream model.';

COMMENT ON COLUMN silver.ticker_universe.snapshot_ticker IS
    'The ticker string as written in the constituent snapshot, retained so the '
    'punctuation normalisation is reversible and auditable.';

COMMENT ON COLUMN silver.ticker_universe.current_gics_sector IS
    'Today''s GICS sector. This is precisely the value a naive join uses for '
    'every historical trade date - the error this project quantifies.';


DROP TABLE IF EXISTS silver.excluded_tickers CASCADE;
CREATE TABLE silver.excluded_tickers (
    ticker          TEXT NOT NULL,
    present_in      TEXT NOT NULL,
    exclusion_reason TEXT NOT NULL,
    CONSTRAINT pk_excluded_tickers PRIMARY KEY (ticker, present_in)
);

COMMENT ON TABLE silver.excluded_tickers IS
    'Tickers dropped from the analysis universe and why. Exists so that the '
    'gap between the two sources is a reported number rather than a silent '
    'inner-join casualty.';


-- ---------------------------------------------------------------------------
-- silver.stg_sector_events — the SCD2 change feed
-- ---------------------------------------------------------------------------
-- The seed table filtered to the analysable universe and ordered. This is the
-- input the hand-rolled SCD Type 2 process consumes, one event date at a time.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.stg_sector_events CASCADE;
CREATE TABLE silver.stg_sector_events (
    ticker                TEXT NOT NULL,
    company_name          TEXT,
    change_type           TEXT NOT NULL,
    old_gics_sector       TEXT NOT NULL,
    new_gics_sector       TEXT NOT NULL,
    old_gics_sub_industry TEXT,
    new_gics_sub_industry TEXT,
    effective_after_close DATE NOT NULL,
    first_trading_day     DATE NOT NULL,
    source_id             TEXT NOT NULL,
    CONSTRAINT pk_stg_sector_events PRIMARY KEY (ticker, first_trading_day),
    CONSTRAINT ck_event_dates CHECK (first_trading_day > effective_after_close),
    CONSTRAINT ck_change_type CHECK (change_type IN ('reclassification', 'sector_rename'))
);

COMMENT ON COLUMN silver.stg_sector_events.effective_after_close IS
    'Last trading day under the OLD classification. Becomes valid_to on the '
    'row being closed.';

COMMENT ON COLUMN silver.stg_sector_events.first_trading_day IS
    'First trading day under the NEW classification. Becomes valid_from on the '
    'row being opened. Using effective_after_close here instead would '
    'misclassify one full trading day per affected ticker.';


-- ---------------------------------------------------------------------------
-- silver.dim_sector_scd — the point-in-time dimension
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.dim_sector_scd CASCADE;
CREATE TABLE silver.dim_sector_scd (
    sector_key        BIGSERIAL,
    ticker            TEXT    NOT NULL,
    gics_sector       TEXT    NOT NULL,
    gics_sub_industry TEXT,
    valid_from        DATE    NOT NULL,
    valid_to          DATE,
    is_current        BOOLEAN NOT NULL,
    version_number    INTEGER NOT NULL,
    change_reason     TEXT    NOT NULL,
    CONSTRAINT pk_dim_sector_scd PRIMARY KEY (sector_key),
    CONSTRAINT uq_dim_sector_version UNIQUE (ticker, version_number),

    -- An open-ended row is the current row and vice versa. Enforcing the
    -- equivalence in the schema means no process can produce a dimension where
    -- is_current and valid_to disagree - a classic SCD2 corruption.
    CONSTRAINT ck_current_row_is_open CHECK (
        (is_current AND valid_to IS NULL) OR (NOT is_current AND valid_to IS NOT NULL)
    ),
    CONSTRAINT ck_validity_ordered CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_version_positive CHECK (version_number >= 1),
    CONSTRAINT ck_change_reason CHECK (
        change_reason IN ('initial', 'reclassification', 'sector_rename')
    )
);

COMMENT ON TABLE silver.dim_sector_scd IS
    'Slowly Changing Dimension Type 2 over GICS sector. One row per ticker per '
    'sector version, with a half-open validity interval [valid_from, valid_to]. '
    'Built by sql/silver/03_build_dim_sector_scd.sql.';

COMMENT ON COLUMN silver.dim_sector_scd.sector_key IS
    'Surrogate key. Facts should reference this rather than (ticker, date) so '
    'that the grain of the dimension can change without rewriting the fact.';

COMMENT ON COLUMN silver.dim_sector_scd.valid_from IS
    'Inclusive start of validity. The earliest version uses the sentinel '
    '1900-01-01 so the dimension provably covers every trade date in the fact '
    'table, including dates before the price corpus begins.';

COMMENT ON COLUMN silver.dim_sector_scd.valid_to IS
    'Inclusive end of validity. NULL means the row is open (current).';

COMMENT ON COLUMN silver.dim_sector_scd.change_reason IS
    'Why this version exists: initial = reconstructed opening state; '
    'reclassification = the company moved sector; sector_rename = the sector '
    'was renamed underneath an unmoved company.';


-- ---------------------------------------------------------------------------
-- silver.fact_returns — daily returns per ticker
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.fact_returns CASCADE;
CREATE TABLE silver.fact_returns (
    ticker       TEXT   NOT NULL,
    trade_date   DATE   NOT NULL,
    close_price  DOUBLE PRECISION NOT NULL,
    prev_close   DOUBLE PRECISION,
    daily_return DOUBLE PRECISION,
    log_return   DOUBLE PRECISION,
    volume       BIGINT,
    CONSTRAINT pk_fact_returns PRIMARY KEY (ticker, trade_date)
);

COMMENT ON TABLE silver.fact_returns IS
    'Daily simple and log returns per ticker, computed with LAG over the '
    'price series. The grain is one row per ticker per trading day.';

COMMENT ON COLUMN silver.fact_returns.daily_return IS
    'Simple return: close / prev_close - 1. NULL on a ticker''s first observed '
    'day, where no previous close exists. NULL is correct here - substituting '
    'zero would inject a fabricated flat day into every cumulative series.';

COMMENT ON COLUMN silver.fact_returns.log_return IS
    'ln(close / prev_close). Additive across time, which makes period '
    'aggregation a SUM rather than a compounding product.';
