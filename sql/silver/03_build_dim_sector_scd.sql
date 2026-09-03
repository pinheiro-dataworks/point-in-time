-- ===========================================================================
-- 03_build_dim_sector_scd.sql — hand-rolled Slowly Changing Dimension Type 2
-- ===========================================================================
-- The mechanism, written out. No dbt macro, no ORM, no framework: just the
-- close-the-old-row / open-the-new-row cycle that every SCD2 implementation
-- reduces to. dbt reproduces this same result in dbt_pit/snapshots/ — having
-- both is the point, because being able to read a snapshot config is not the
-- same as understanding what it does.
--
-- The problem being solved
-- -----------------------
-- The sources give us the *arrival state* (today's sector per ticker) and a
-- *change log* (which tickers moved, when, and from what). Neither is the
-- history. The history has to be reconstructed by taking today's state and
-- walking the change log backwards to recover the opening state, then
-- replaying it forwards to materialise every intermediate version.
--
--   Step 1  Stage the change events, scoped to the analysable universe.
--   Step 2  Reconstruct each ticker's OPENING sector and open version 1.
--   Step 3  Replay events in chronological order, closing and opening rows.
--   Step 4  Reconcile the result against the arrival state.
--
-- Depends on: silver.ticker_universe, bronze.sector_history
-- Produces:   silver.stg_sector_events, silver.dim_sector_scd,
--             silver.dim_reconciliation
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- Step 1 — stage the change events
-- ---------------------------------------------------------------------------
-- Scoped to the analysable universe. Seed rows for delisted tickers (TWTR,
-- ATVI, TRIP, ETSY) are intentionally left behind here: they are real history,
-- but with no price series they cannot contribute to a return calculation.
-- The seed keeps them; the dimension cannot use them. See
-- docs/sector_sources.md section 6.1.
-- ---------------------------------------------------------------------------
TRUNCATE TABLE silver.stg_sector_events;

INSERT INTO silver.stg_sector_events (
    ticker, company_name, change_type,
    old_gics_sector, new_gics_sector,
    old_gics_sub_industry, new_gics_sub_industry,
    effective_after_close, first_trading_day, source_id
)
SELECT
    h.ticker, h.company_name, h.change_type,
    h.old_gics_sector, h.new_gics_sector,
    h.old_gics_sub_industry, h.new_gics_sub_industry,
    h.effective_after_close, h.first_trading_day, h.source_id
FROM bronze.sector_history h
JOIN silver.ticker_universe u ON u.ticker = h.ticker;


-- ---------------------------------------------------------------------------
-- Step 2 — reconstruct the opening state
-- ---------------------------------------------------------------------------
-- A ticker's sector at the start of history is:
--   * the `old_gics_sector` of its EARLIEST change event, if it has one;
--   * otherwise its current sector, because it never moved.
--
-- valid_from is the sentinel 1900-01-01 rather than the ticker's first trade
-- date. That is deliberate: the dimension must provably cover every possible
-- trade date, so that the Gold range join can be an INNER join and any
-- unmatched fact row is a real defect rather than an expected edge case.
-- ---------------------------------------------------------------------------
TRUNCATE TABLE silver.dim_sector_scd RESTART IDENTITY;

INSERT INTO silver.dim_sector_scd (
    ticker, gics_sector, gics_sub_industry,
    valid_from, valid_to, is_current, version_number, change_reason
)
SELECT
    u.ticker,
    -- CASE, not COALESCE: for a ticker that DID change, the historical
    -- sub-industry is legitimately NULL when no source document recorded it.
    -- COALESCE would quietly substitute today's sub-industry there — writing
    -- the present into the past, which is the exact bug this project exists
    -- to demonstrate.
    CASE WHEN first_event.ticker IS NOT NULL
         THEN first_event.old_gics_sector
         ELSE u.current_gics_sector
    END,
    CASE WHEN first_event.ticker IS NOT NULL
         THEN first_event.old_gics_sub_industry
         ELSE u.current_sub_industry
    END,
    DATE '1900-01-01',
    NULL,
    TRUE,
    1,
    'initial'
FROM silver.ticker_universe u
LEFT JOIN LATERAL (
    SELECT e.ticker, e.old_gics_sector, e.old_gics_sub_industry
    FROM silver.stg_sector_events e
    WHERE e.ticker = u.ticker
    ORDER BY e.first_trading_day
    LIMIT 1
) AS first_event ON TRUE;


-- ---------------------------------------------------------------------------
-- Step 3 — replay the change events in chronological order
-- ---------------------------------------------------------------------------
-- Each iteration performs the two statements that ARE Slowly Changing
-- Dimension Type 2:
--
--   UPDATE  close the currently-open row  (valid_to := last old-classification
--                                          trading day; is_current := FALSE)
--   INSERT  open the new row              (valid_from := first new-
--                                          classification trading day)
--
-- The loop is over distinct event DATES, not over rows. All tickers sharing an
-- event date are closed and opened in one set-based pair of statements, so the
-- cost is O(number of distinct event dates) — two, here — rather than O(rows).
-- It stays correct for any number of future GICS reviews.
--
-- Ordering by date is not cosmetic. A ticker reclassified twice must have its
-- first change applied before its second, or the second UPDATE would close the
-- wrong row and the validity chain would break.
-- ---------------------------------------------------------------------------
DO $scd$
DECLARE
    event_date   DATE;
    rows_closed  INTEGER;
    rows_opened  INTEGER;
BEGIN
    FOR event_date IN
        SELECT DISTINCT first_trading_day
        FROM silver.stg_sector_events
        ORDER BY first_trading_day
    LOOP
        -- --- close the open row for every ticker changing on this date ------
        UPDATE silver.dim_sector_scd AS d
        SET valid_to   = e.effective_after_close,
            is_current = FALSE
        FROM silver.stg_sector_events AS e
        WHERE e.first_trading_day = event_date
          AND d.ticker            = e.ticker
          AND d.is_current;

        GET DIAGNOSTICS rows_closed = ROW_COUNT;

        -- --- open the new version ------------------------------------------
        -- version_number is derived from the ticker's existing maximum rather
        -- than from a counter, so the statement is idempotent with respect to
        -- how many versions already exist.
        INSERT INTO silver.dim_sector_scd (
            ticker, gics_sector, gics_sub_industry,
            valid_from, valid_to, is_current, version_number, change_reason
        )
        SELECT
            e.ticker,
            e.new_gics_sector,
            e.new_gics_sub_industry,
            e.first_trading_day,
            NULL,
            TRUE,
            (SELECT MAX(d.version_number) + 1
             FROM silver.dim_sector_scd AS d
             WHERE d.ticker = e.ticker),
            e.change_type
        FROM silver.stg_sector_events AS e
        WHERE e.first_trading_day = event_date;

        GET DIAGNOSTICS rows_opened = ROW_COUNT;

        RAISE NOTICE 'SCD2 % : closed % row(s), opened % row(s)',
            event_date, rows_closed, rows_opened;

        -- Every closed row must be replaced by exactly one open row. If these
        -- ever diverge the dimension has either orphaned a ticker or created a
        -- gap, and continuing would bake the corruption into the Gold layer.
        IF rows_closed <> rows_opened THEN
            RAISE EXCEPTION
                'SCD2 integrity failure on %: closed % rows but opened % rows',
                event_date, rows_closed, rows_opened;
        END IF;
    END LOOP;
END
$scd$;


-- ---------------------------------------------------------------------------
-- Step 4 — reconcile against the arrival state
-- ---------------------------------------------------------------------------
-- The dimension was reconstructed by walking backwards from today's sector and
-- replaying forwards. Replaying should therefore land back exactly on today's
-- sector. Where it does not, one of two things is true:
--
--   * the seed is missing a reclassification event for that ticker; or
--   * the snapshot reflects a change more recent than the seed covers.
--
-- Either way it is a real finding, so it is materialised as a table and
-- asserted by a test rather than silently tolerated.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.dim_reconciliation;
CREATE TABLE silver.dim_reconciliation AS
SELECT
    u.ticker,
    u.security_name,
    u.current_gics_sector          AS snapshot_sector,
    d.gics_sector                  AS dimension_current_sector,
    d.version_number               AS versions_built,
    d.valid_from                   AS current_version_from
FROM silver.ticker_universe   AS u
JOIN silver.dim_sector_scd    AS d
  ON d.ticker = u.ticker
 AND d.is_current
WHERE d.gics_sector IS DISTINCT FROM u.current_gics_sector;

COMMENT ON TABLE silver.dim_reconciliation IS
    'Tickers whose replayed SCD2 end-state disagrees with the current '
    'constituent snapshot. Expected to be empty; a non-empty result means the '
    'seed is missing an event, or the snapshot moved ahead of the seed.';

-- ---------------------------------------------------------------------------
-- Step 5 - the sector-existence invariant
-- ---------------------------------------------------------------------------
-- A dimension row must never claim a sector for a date on which that sector
-- did not exist under GICS. This is a genuinely independent check: it does not
-- consult the seed at all, only the sector registry, so it catches tickers the
-- seed *forgot*.
--
-- It has already earned its place. A first version of this pipeline assumed
-- that any ticker absent from the seed had never changed sector. For eight
-- tickers whose current sector is Communication Services that assumption was
-- provably false - the sector did not exist until 2018-09-24 - and this query
-- is what surfaced them. Two (LYV, TMUS) were resolved by extending the seed;
-- six were held out in excluded_entities.csv.
--
-- Scoped to the analysis window because the 1900-01-01 sentinel would
-- otherwise flag every Real Estate ticker: that sector was created
-- 2016-09-19, before the window opens, which is precisely why the window
-- opens where it does.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS silver.sector_existence_violations;
CREATE TABLE silver.sector_existence_violations AS
SELECT
    d.ticker,
    d.gics_sector,
    d.version_number,
    d.valid_from,
    d.valid_to,
    r.existed_from AS sector_existed_from,
    r.existed_to   AS sector_existed_to,
    CASE
        WHEN GREATEST(d.valid_from, w.start_date) < r.existed_from
            THEN 'claims sector before it existed'
        ELSE 'claims sector after it was retired'
    END AS violation
FROM silver.dim_sector_scd     AS d
JOIN bronze.gics_sector_registry AS r ON r.gics_sector = d.gics_sector
CROSS JOIN silver.analysis_window AS w
WHERE
    -- The version must actually overlap the analysis window to matter.
    d.valid_from <= w.end_date
    AND COALESCE(d.valid_to, DATE '9999-12-31') >= w.start_date
    AND (
        -- Claimed before the sector came into existence...
        GREATEST(d.valid_from, w.start_date) < r.existed_from
        -- ...or still claimed after the sector was retired.
        OR (
            r.existed_to IS NOT NULL
            AND LEAST(COALESCE(d.valid_to, DATE '9999-12-31'), w.end_date) > r.existed_to
        )
    );

COMMENT ON TABLE silver.sector_existence_violations IS
    'Dimension rows asserting a sector on dates when that sector did not exist '
    'under GICS. Expected to be empty. A non-empty result means the seed is '
    'missing a reclassification for that ticker - the "never changed" default '
    'is wrong and is silently back-dating a sector that had not been created.';

ANALYZE silver.stg_sector_events;
ANALYZE silver.dim_sector_scd;
ANALYZE silver.dim_reconciliation;
ANALYZE silver.sector_existence_violations;
