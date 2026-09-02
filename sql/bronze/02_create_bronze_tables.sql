-- ===========================================================================
-- 02_create_bronze_tables.sql - raw landing tables
-- ===========================================================================
-- Bronze holds source data verbatim. The only liberties taken are:
--   * renaming OHLCV columns away from SQL-reserved words (`open` -> `open_price`);
--   * typing dates as DATE rather than TEXT, because every downstream join is
--     temporal and a text date would silently break range comparisons.
--
-- Notably absent: NOT NULL on the price columns. Some tickers have genuine
-- gaps (trading halts, IPO dates mid-corpus) and bronze's job is to record
-- what the source said, not to assert what it should have said. Those
-- assertions belong in silver, where they are testable.
--
-- DDL is CREATE TABLE IF NOT EXISTS, and the loader TRUNCATEs only the tables
-- it is about to populate. That is what makes `ingest --skip-prices` safe:
-- with DROP/CREATE it would silently destroy the 1.2M-row price table it
-- claims to be skipping. Use `ingest --recreate` to force a clean rebuild.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS bronze.daily_prices (
    ticker       TEXT   NOT NULL,
    trade_date   DATE   NOT NULL,
    open_price   DOUBLE PRECISION,
    high_price   DOUBLE PRECISION,
    low_price    DOUBLE PRECISION,
    close_price  DOUBLE PRECISION,
    volume       BIGINT,
    CONSTRAINT pk_daily_prices PRIMARY KEY (ticker, trade_date)
);

COMMENT ON TABLE bronze.daily_prices IS
    'Daily OHLCV per S&P 500 constituent, 2015-12-21 to 2025-12-19. Source: '
    'Kaggle "S&P 500 Stocks: Daily Historical Data (10 Years)". Covers current '
    'constituents only - see docs/sector_sources.md section 6.1 for the '
    'survivorship-bias disclosure.';

COMMENT ON COLUMN bronze.daily_prices.close_price IS
    'Adjusted close as published by the source. Splits and dividends are '
    'already reflected, which is why returns are computed directly from it.';


CREATE TABLE IF NOT EXISTS bronze.sp500_current_snapshot (
    ticker            TEXT NOT NULL,
    security_name     TEXT,
    gics_sector       TEXT,
    gics_sub_industry TEXT,
    headquarters      TEXT,
    date_added        DATE,
    cik               TEXT,
    founded           TEXT,
    CONSTRAINT pk_sp500_current_snapshot PRIMARY KEY (ticker)
);

COMMENT ON TABLE bronze.sp500_current_snapshot IS
    'Current S&P 500 constituents with their CURRENT GICS classification. '
    'Source: fja05680/sp500 (MIT). This is the "arrival state" the SCD Type 2 '
    'dimension is reconstructed backwards from, and it is also exactly what a '
    'naive join would use for every historical trade date.';

COMMENT ON COLUMN bronze.sp500_current_snapshot.cik IS
    'SEC Central Index Key. Stored as TEXT to preserve leading zeros. It is '
    'the only stable entity identifier available here, though it is not used '
    'as a join key because the price corpus carries only tickers.';

COMMENT ON COLUMN bronze.sp500_current_snapshot.founded IS
    'Free text in the source (values such as "1902", "1888 (1969)"). Left as '
    'TEXT deliberately - coercing it would discard information bronze exists '
    'to preserve.';


CREATE TABLE IF NOT EXISTS bronze.sp500_membership (
    ticker     TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date   DATE,
    CONSTRAINT pk_sp500_membership PRIMARY KEY (ticker, start_date)
);

COMMENT ON TABLE bronze.sp500_membership IS
    'Index membership intervals since 1996. Source: fja05680/sp500 '
    '(sp500_ticker_start_end.csv). A NULL end_date means the ticker is still '
    'a constituent. This table is itself an SCD Type 2 structure produced by '
    'someone else, and is used to scope the analysis to genuine constituents.';

COMMENT ON COLUMN bronze.sp500_membership.end_date IS
    'NULL = currently a constituent. Note a ticker may appear more than once '
    'with disjoint intervals (removed then re-added), which is why the primary '
    'key includes start_date.';


CREATE TABLE IF NOT EXISTS bronze.sector_history (
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
    CONSTRAINT pk_sector_history PRIMARY KEY (ticker, first_trading_day)
);

COMMENT ON TABLE bronze.sector_history IS
    'The curated sector-reclassification seed - the only hand-assembled table '
    'in the project. Every row is transcribed from a documented GICS '
    'classification-committee decision. See docs/sector_sources.md for the '
    'source backing each row. Loaded from dbt_pit/seeds/sector_history.csv, '
    'which is also consumed by `dbt seed`, so the hand-rolled SQL path and the '
    'dbt path read one identical source of truth.';

COMMENT ON COLUMN bronze.sector_history.change_type IS
    'reclassification = the company moved to a different sector. '
    'sector_rename = the company did not move; its sector was renamed '
    '(Telecommunication Services -> Communication Services, 2018). The '
    'distinction matters: only reclassifications misattribute history, so the '
    'anchor metric counts them separately.';

COMMENT ON COLUMN bronze.sector_history.source_id IS
    'Foreign key into the source register in docs/sector_sources.md section 2.';


CREATE TABLE IF NOT EXISTS bronze.gics_sector_registry (
    gics_sector  TEXT NOT NULL,
    existed_from DATE NOT NULL,
    existed_to   DATE,
    source_id    TEXT NOT NULL,
    notes        TEXT,
    CONSTRAINT pk_gics_sector_registry PRIMARY KEY (gics_sector)
);

COMMENT ON TABLE bronze.gics_sector_registry IS
    'When each GICS sector label was in force. Makes "this sector did not '
    'exist yet" a checkable fact rather than a comment: the invariant in '
    'silver.sector_existence_violations joins against it. Sectors present '
    'since the 1999 GICS inception carry the 1900-01-01 sentinel, meaning '
    'simply "before the analysis window".';

COMMENT ON COLUMN bronze.gics_sector_registry.existed_to IS
    'NULL = still in force. Only Telecommunication Services is closed, having '
    'been renamed to Communication Services after close 2018-09-21.';


CREATE TABLE IF NOT EXISTS bronze.excluded_entities (
    ticker           TEXT NOT NULL,
    company_name     TEXT,
    exclusion_class  TEXT NOT NULL,
    exclusion_reason TEXT NOT NULL,
    CONSTRAINT pk_excluded_entities PRIMARY KEY (ticker),
    CONSTRAINT ck_exclusion_class CHECK (
        exclusion_class IN ('entity_discontinuity', 'unverified_sector_history')
    )
);

COMMENT ON TABLE bronze.excluded_entities IS
    'Tickers deliberately held out of the analysis universe, with the reason '
    'for each. Two classes: entity_discontinuity, where the price series is '
    'backfilled across a corporate restructuring so early observations belong '
    'to a different company; and unverified_sector_history, where the ticker''s '
    'current sector post-dates part of the window and no source documents what '
    'it was before. Both are recorded rather than silently filtered.';
