-- silver.sector_existence_violations is materialised by
-- sql/silver/03_build_dim_sector_scd.sql, checking every dimension row
-- against bronze.gics_sector_registry: no row may claim a sector on a date
-- when that sector did not exist under GICS. This is the check that caught
-- LYV and TMUS missing from the original seed - see that script's Step 5
-- comment for the full story. Promoted here into a CI gate so a future seed
-- edit that reintroduces a similar gap fails the build instead of silently
-- back-dating a sector that had not been created yet.

select *
from {{ source('silver_pipeline', 'sector_existence_violations') }}
