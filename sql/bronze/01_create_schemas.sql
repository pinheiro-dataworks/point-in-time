-- ===========================================================================
-- 01_create_schemas.sql — medallion schema layout
-- ===========================================================================
-- The warehouse is organised into three schemas rather than three name
-- prefixes in one schema. This buys two things that matter later:
--
--   * grants can be issued per layer (a BI user gets `gold`, nothing else);
--   * dbt's `schema` config maps 1:1 onto these, so the models it builds land
--     beside the hand-rolled SQL objects instead of in a parallel namespace.
--
-- Idempotent: safe to re-run on every `make build`.
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA bronze IS
    'Raw ingested data, landed as-is. No transformation, no deduplication, no '
    'type coercion beyond what the load requires. Reproducible from source.';

COMMENT ON SCHEMA silver IS
    'Conformed and modelled data. Contains the SCD Type 2 sector dimension and '
    'the returns fact table.';

COMMENT ON SCHEMA gold IS
    'Business-facing aggregates. The naive vs. point-in-time comparison that '
    'produces the anchor metric, plus the artefacts the dashboard reads.';
