# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] — 2026-10-16

Initial release.

### Added

- Bronze/Silver/Gold SQL pipeline (`sql/`) ingesting S&P 500 constituents,
  daily OHLCV prices, and a sourced GICS sector-reclassification table.
- Hand-rolled SCD Type 2 sector dimension (`silver.dim_sector_scd`) and a
  dbt-snapshot counterpart (`silver.dim_sector_scd_dbt`), kept side by side
  to show both the underlying mechanism and its production-automation form.
- Point-in-time range join (`gold.fact_returns_pit`) comparing naive
  (today's-label) and point-in-time-correct sector returns, and the
  `gold.anchor_metric` headline comparison.
- dbt project (`dbt_pit/`) with seeds, a snapshot, sources, and 35 data
  tests covering temporal integrity (no overlapping or gapped validity
  ranges, exactly one current row per ticker, fact-to-dimension referential
  integrity, sector-existence checks).
- `EXPLAIN ANALYZE` benchmark suite (`src/pit_lab/benchmark.py`) and its
  generated report (`docs/performance.md`), including two benchmarks where
  indexing does not help.
- Streamlit dashboard (`dashboard/`), 8 pages, serving from committed
  Gold-layer Parquet with no database dependency at runtime.
- GitHub Actions CI (`dbt build && dbt test`) on push, pull request, and a
  weekly schedule.
- pytest suite (`tests/`), 31 tests, requiring no live database.
- Source register for the sector-reclassification seed table
  (`docs/sector_sources.md`) and design-decision record (`docs/DESIGN.md`).
