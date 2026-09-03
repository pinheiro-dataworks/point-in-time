-- silver.dim_reconciliation is materialised by
-- sql/silver/03_build_dim_sector_scd.sql itself as the output of replaying
-- the SCD2 build forward and comparing it to the current-state snapshot. A
-- non-empty result means the seed is missing an event, or the snapshot has
-- moved ahead of the seed. This test just asserts that check landed empty -
-- it is a promotion of an already-computed diagnostic into a CI gate.

select *
from {{ source('silver_pipeline', 'dim_reconciliation') }}
