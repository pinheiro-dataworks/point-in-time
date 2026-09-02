-- ===========================================================================
-- 00_drop_bronze.sql - force a clean Bronze rebuild
-- ===========================================================================
-- Only runs under `python -m pit_lab.ingest --recreate`. Normal loads use
-- CREATE TABLE IF NOT EXISTS plus a targeted TRUNCATE, so that reloading the
-- small reference tables cannot destroy the large price table.
--
-- CASCADE is required because the Silver layer builds views and tables that
-- depend on these; they are rebuilt from scratch by the Silver scripts.
-- ===========================================================================

DROP TABLE IF EXISTS bronze.daily_prices           CASCADE;
DROP TABLE IF EXISTS bronze.sp500_current_snapshot CASCADE;
DROP TABLE IF EXISTS bronze.sp500_membership       CASCADE;
DROP TABLE IF EXISTS bronze.sector_history         CASCADE;
DROP TABLE IF EXISTS bronze.gics_sector_registry   CASCADE;
DROP TABLE IF EXISTS bronze.excluded_entities      CASCADE;
