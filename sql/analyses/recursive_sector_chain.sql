-- ===========================================================================
-- recursive_sector_chain.sql - walk a ticker's full sector version chain
-- ===========================================================================
-- Analysis queries live outside sql/silver and sql/gold on purpose: the build
-- orchestrator only picks up NN_-prefixed files, so nothing here runs as part
-- of a pipeline. These are meant to be read and executed by hand.
--
-- WHY RECURSION, HONESTLY
-- -----------------------
-- An SCD Type 2 table is a linked list per key: each version points at the
-- next by way of valid_to + 1 day = the next version's valid_from. A recursive
-- CTE is the tool that walks that structure without knowing its depth in
-- advance.
--
-- Worth being straight about the data, though: the two seeded GICS events
-- never touch the same ticker, so no ticker in this warehouse has more than
-- two versions. The recursion terminates at depth 2. It is not window dressing
-- - it is the correct construct for an arbitrary-length chain, and it keeps
-- working unmodified when a third GICS review is appended to the seed - but
-- claiming it is doing heavy lifting on this dataset would be dishonest.
--
-- The chain is walked by DATE ADJACENCY rather than by version_number. Using
-- version_number would make the recursion trivial (n + 1) and would prove
-- nothing about the validity intervals. Walking by date proves the chain has
-- no gaps: if any version's valid_to + 1 day fails to land on the next
-- version's valid_from, the recursion stops early and the ticker's chain comes
-- back short.
-- ===========================================================================

WITH RECURSIVE sector_chain AS (

    -- --- anchor: the oldest version of the chosen ticker -------------------
    SELECT
        d.ticker,
        d.gics_sector,
        d.gics_sub_industry,
        d.valid_from,
        d.valid_to,
        d.is_current,
        d.change_reason,
        1 AS depth,
        d.gics_sector::TEXT AS sector_path
    FROM silver.dim_sector_scd AS d
    WHERE d.ticker = 'GOOGL'
      AND d.version_number = 1

    UNION ALL

    -- --- recursive step: the version that starts the day after this one ----
    SELECT
        nxt.ticker,
        nxt.gics_sector,
        nxt.gics_sub_industry,
        nxt.valid_from,
        nxt.valid_to,
        nxt.is_current,
        nxt.change_reason,
        chain.depth + 1,
        chain.sector_path || ' -> ' || nxt.gics_sector
    FROM sector_chain AS chain
    JOIN silver.dim_sector_scd AS nxt
      ON  nxt.ticker     = chain.ticker
      -- Date adjacency. Any gap in the validity chain breaks this join and
      -- the walk stops - which is exactly the failure we want to be visible.
      AND nxt.valid_from = chain.valid_to + INTERVAL '1 day'
)
SELECT
    ticker,
    depth,
    gics_sector,
    gics_sub_industry,
    valid_from,
    COALESCE(valid_to::TEXT, 'current') AS valid_to,
    change_reason,
    sector_path
FROM sector_chain
ORDER BY depth;

-- Expected output for GOOGL:
--
--  depth 1 | Information Technology | Internet Software and Services | 1900-01-01 | 2018-09-21 | initial
--  depth 2 | Communication Services | Interactive Media and Services | 2018-09-24 | current    | reclassification
--
-- Note the one-day gap between 2018-09-21 and 2018-09-24 is a WEEKEND, not a
-- hole in the chain. `valid_to + INTERVAL '1 day'` is 2018-09-22, a Saturday,
-- which does not equal the next valid_from of 2018-09-24.
--
-- That means the naive adjacency join above walks GOOGL's chain to depth 1
-- only. This is a real property of modelling validity on TRADING days while
-- walking the chain in CALENDAR days, and it is left visible here rather than
-- papered over. The gap-tolerant version below is the one that actually works.


-- ===========================================================================
-- Gap-tolerant chain walk - the version to use
-- ===========================================================================
-- Instead of requiring calendar adjacency, step to the next version by
-- ordering: the successor is the version with the smallest valid_from greater
-- than this one's. This is correct whether the boundary falls on a weekend, a
-- holiday, or a consecutive trading day.
-- ===========================================================================

WITH RECURSIVE sector_chain AS (

    SELECT
        d.ticker,
        d.gics_sector,
        d.valid_from,
        d.valid_to,
        d.change_reason,
        1 AS depth,
        d.gics_sector::TEXT AS sector_path
    FROM silver.dim_sector_scd AS d
    WHERE d.ticker = 'GOOGL'
      AND d.version_number = 1

    UNION ALL

    SELECT
        nxt.ticker,
        nxt.gics_sector,
        nxt.valid_from,
        nxt.valid_to,
        nxt.change_reason,
        chain.depth + 1,
        chain.sector_path || ' -> ' || nxt.gics_sector
    FROM sector_chain AS chain
    -- LATERAL + LIMIT 1 selects the immediate successor rather than every
    -- later version, which is what keeps the walk a chain instead of a
    -- fan-out. Without it, a ticker with three versions would yield the
    -- transitive closure rather than the path.
    JOIN LATERAL (
        SELECT d2.*
        FROM silver.dim_sector_scd AS d2
        WHERE d2.ticker     = chain.ticker
          AND d2.valid_from > chain.valid_from
        ORDER BY d2.valid_from
        LIMIT 1
    ) AS nxt ON TRUE
)
SELECT
    ticker,
    depth,
    gics_sector,
    valid_from,
    COALESCE(valid_to::TEXT, 'current') AS valid_to,
    change_reason,
    sector_path
FROM sector_chain
ORDER BY depth;


-- ===========================================================================
-- Every multi-version ticker, as one chain per row
-- ===========================================================================
-- The same recursion applied across the whole dimension, keeping only the
-- deepest row per ticker so each chain collapses to a single readable path.
-- ===========================================================================

WITH RECURSIVE all_chains AS (

    SELECT
        d.ticker,
        d.valid_from,
        1 AS depth,
        d.gics_sector::TEXT AS sector_path
    FROM silver.dim_sector_scd AS d
    WHERE d.version_number = 1

    UNION ALL

    SELECT
        nxt.ticker,
        nxt.valid_from,
        chain.depth + 1,
        chain.sector_path || ' -> ' || nxt.gics_sector
    FROM all_chains AS chain
    JOIN LATERAL (
        SELECT d2.*
        FROM silver.dim_sector_scd AS d2
        WHERE d2.ticker     = chain.ticker
          AND d2.valid_from > chain.valid_from
        ORDER BY d2.valid_from
        LIMIT 1
    ) AS nxt ON TRUE
)
SELECT DISTINCT ON (ticker)
    ticker,
    depth AS versions,
    sector_path
FROM all_chains
WHERE depth > 1
ORDER BY ticker, depth DESC;
