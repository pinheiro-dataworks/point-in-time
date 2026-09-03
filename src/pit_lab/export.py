"""Gold-layer export: PostgreSQL to Parquet.

The Streamlit dashboard does not connect to PostgreSQL at all — see
requirements.txt for why. Instead it reads a handful of Parquet files, via
DuckDB, from ``data/processed/``. This module produces those files from the
warehouse.

Parquet rather than CSV for three reasons that matter at this row count:
columnar storage make the dashboard's per-sector filters fast, native typing
means dates and floats survive the round trip without a re-parse step, and
compression keeps the exported artefacts small enough to commit to the
repository (see the .gitignore note on why that matters for a Streamlit
Community Cloud deploy with no build-time database).

Run as a module::

    python -m pit_lab.export
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from pit_lab.config import get_settings

logger = logging.getLogger(__name__)

# Table -> output filename. Kept as an explicit mapping rather than a
# convention (e.g. "same as table name") so the dashboard's file list and this
# module's export list can be diffed against each other directly.
EXPORTS: dict[str, str] = {
    "gold.anchor_metric": "anchor_metric.parquet",
    "gold.sector_cumulative_returns": "sector_cumulative_returns.parquet",
    "gold.sector_daily_returns": "sector_daily_returns.parquet",
    "silver.dim_sector_scd": "dim_sector_scd.parquet",
    "silver.ticker_universe": "ticker_universe.parquet",
    "silver.excluded_tickers": "excluded_tickers.parquet",
}


def export_table(engine, table: str, out_path: Path) -> int:
    """Export one table to a Parquet file. Returns the row count exported."""
    frame = pd.read_sql_table(table.split(".")[1], con=engine, schema=table.split(".")[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False, compression="zstd")
    return len(frame)


def export_all() -> dict[str, int]:
    """Export every table in :data:`EXPORTS`. Returns rows exported per file."""
    settings = get_settings()
    settings.paths.processed.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.db.sqlalchemy_url)

    exported: dict[str, int] = {}
    try:
        for table, filename in EXPORTS.items():
            out_path = settings.paths.processed / filename
            rows = export_table(engine, table, out_path)
            exported[filename] = rows
            logger.info("Exported %s -> %s (%s rows)", table, filename, f"{rows:,}")
    finally:
        engine.dispose()

    return exported


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the Gold layer to Parquet.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    exported = export_all()

    print("\nExported to data/processed/:")
    total_rows = 0
    for filename, rows in exported.items():
        print(f"  {filename:<34} {rows:>10,} rows")
        total_rows += rows
    print(f"  {'TOTAL':<34} {total_rows:>10,} rows")

    return 0


if __name__ == "__main__":
    sys.exit(main())
