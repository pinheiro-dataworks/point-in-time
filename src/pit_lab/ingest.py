"""Bronze-layer ingestion: raw CSV to PostgreSQL.

Three sources are landed:

1. **Daily OHLCV** — 501 per-ticker CSVs exported from Kaggle in yfinance's
   MultiIndex layout, reshaped into one long table.
2. **Current constituent snapshot** — ticker, security name and *current* GICS
   classification.
3. **Index membership intervals** — when each ticker entered and left the index.

Loading uses PostgreSQL's ``COPY`` rather than ``INSERT``. For ~1.26M price
rows the difference is roughly two orders of magnitude, and it keeps a full
rebuild inside a few seconds — which matters because the whole project is meant
to be reproducible with one command.

Run as a module::

    python -m pit_lab.ingest
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from pit_lab.config import get_settings
from pit_lab.db import connect, run_script

logger = logging.getLogger(__name__)

# The Kaggle export carries a three-row header inherited from a yfinance
# MultiIndex dump:
#
#   row 0:  Price,Close,High,Low,Open,Volume    <- real column names
#   row 1:  Ticker,AAPL,AAPL,AAPL,AAPL,AAPL     <- redundant, one ticker per file
#   row 2:  Date,,,,,                           <- index-name row, empty
#   row 3+: 2015-12-21,24.19,...                <- data
#
# Rows 1 and 2 carry no information the filename does not already give us.
# Verified identical across all 501 files before relying on it.
_HEADER_ROWS_TO_SKIP = [1, 2]

# The source names the index column "Price"; it holds the trade date.
_SOURCE_DATE_COLUMN = "Price"

_COLUMN_RENAMES = {
    "Open": "open_price",
    "High": "high_price",
    "Low": "low_price",
    "Close": "close_price",
    "Volume": "volume",
}

_PRICE_COLUMNS = [
    "ticker",
    "trade_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
]


class IngestionError(RuntimeError):
    """Raised when a source file cannot be parsed into the expected shape."""


# --------------------------------------------------------------------------
# Price data
# --------------------------------------------------------------------------
def read_price_file(path: Path) -> pd.DataFrame:
    """Parse one per-ticker OHLCV CSV into long format.

    Args:
        path: Path to ``<TICKER>.csv``.

    Returns:
        A frame with columns matching :data:`_PRICE_COLUMNS`. The ticker is
        taken from the filename, not from the file's redundant Ticker row.

    Raises:
        IngestionError: If the file does not have the expected column layout.
    """
    ticker = path.stem

    frame = pd.read_csv(
        path,
        skiprows=_HEADER_ROWS_TO_SKIP,
        parse_dates=[_SOURCE_DATE_COLUMN],
    )

    missing = {_SOURCE_DATE_COLUMN, *_COLUMN_RENAMES}.difference(frame.columns)
    if missing:
        raise IngestionError(f"{path.name}: missing expected columns {sorted(missing)}")

    frame = frame.rename(columns={_SOURCE_DATE_COLUMN: "trade_date", **_COLUMN_RENAMES})
    frame["ticker"] = ticker
    frame["trade_date"] = frame["trade_date"].dt.date

    # Volume arrives as float because pandas widens integer columns containing
    # NaN. Int64 (nullable) keeps it an integer without inventing a value for
    # the gaps.
    frame["volume"] = frame["volume"].astype("Int64")

    return frame[_PRICE_COLUMNS]


def read_all_prices(prices_dir: Path) -> pd.DataFrame:
    """Read every ticker CSV in a directory into one long frame.

    Files that fail to parse are reported and skipped rather than aborting the
    run: with 501 files, one malformed export should not cost a full rebuild.
    The count of skipped files is logged so the failure is never silent.
    """
    files = sorted(prices_dir.glob("*.csv"))
    if not files:
        raise IngestionError(
            f"No CSV files found in {prices_dir}. "
            "Expected the per-ticker OHLCV export - see README section 'Data'."
        )

    logger.info("Reading %d price files from %s", len(files), prices_dir)
    frames: list[pd.DataFrame] = []
    failures: list[tuple[str, str]] = []

    for path in files:
        try:
            frames.append(read_price_file(path))
        except (IngestionError, pd.errors.ParserError, ValueError) as exc:
            failures.append((path.name, str(exc)))

    if failures:
        logger.warning("Skipped %d unparseable file(s):", len(failures))
        for name, reason in failures:
            logger.warning("  %s - %s", name, reason)

    if not frames:
        raise IngestionError(f"Every file in {prices_dir} failed to parse.")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "Parsed %s rows across %d tickers (%s to %s)",
        f"{len(combined):,}",
        combined["ticker"].nunique(),
        combined["trade_date"].min(),
        combined["trade_date"].max(),
    )
    return combined


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
def read_current_snapshot(path: Path) -> pd.DataFrame:
    """Parse the current-constituent GICS snapshot."""
    frame = pd.read_csv(path)
    frame = frame.rename(
        columns={
            "Symbol": "ticker",
            "Security": "security_name",
            "GICS Sector": "gics_sector",
            "GICS Sub-Industry": "gics_sub_industry",
            "Headquarters Location": "headquarters",
            "Date added": "date_added",
            "CIK": "cik",
            "Founded": "founded",
        }
    )

    frame["date_added"] = pd.to_datetime(frame["date_added"], errors="coerce").dt.date
    # CIK is an identifier, not a quantity: keep leading zeros, drop the float
    # formatting pandas would otherwise apply.
    frame["cik"] = frame["cik"].astype("Int64").astype("string").str.zfill(10)
    frame["founded"] = frame["founded"].astype("string")

    return frame[
        [
            "ticker",
            "security_name",
            "gics_sector",
            "gics_sub_industry",
            "headquarters",
            "date_added",
            "cik",
            "founded",
        ]
    ]


def read_sector_history(path: Path) -> pd.DataFrame:
    """Parse the curated sector-reclassification seed.

    The file is committed to the repository under ``dbt_pit/seeds/`` because it
    is also a dbt seed. Reading it from that one location keeps the hand-rolled
    SQL path and the dbt path provably in sync — there is no second copy that
    could drift.
    """
    frame = pd.read_csv(path, dtype="string")

    for column in ("effective_after_close", "first_trading_day"):
        frame[column] = pd.to_datetime(frame[column], errors="raise").dt.date

    # A reclassification that does not change sector is a transcription error,
    # not a modelling edge case: fail loudly rather than emit a no-op version.
    same_sector = frame["old_gics_sector"] == frame["new_gics_sector"]
    if same_sector.any():
        offenders = frame.loc[same_sector, "ticker"].tolist()
        raise IngestionError(
            f"sector_history rows with identical old/new sector: {offenders}. "
            "Every row must represent an actual sector change."
        )

    return frame[
        [
            "ticker",
            "company_name",
            "change_type",
            "old_gics_sector",
            "new_gics_sector",
            "old_gics_sub_industry",
            "new_gics_sub_industry",
            "effective_after_close",
            "first_trading_day",
            "source_id",
        ]
    ]


def read_sector_registry(path: Path) -> pd.DataFrame:
    """Parse the GICS sector existence registry."""
    frame = pd.read_csv(path, dtype="string")
    frame["existed_from"] = pd.to_datetime(frame["existed_from"], errors="raise").dt.date
    frame["existed_to"] = pd.to_datetime(frame["existed_to"], errors="coerce").dt.date
    return frame[["gics_sector", "existed_from", "existed_to", "source_id", "notes"]]


def read_excluded_entities(path: Path) -> pd.DataFrame:
    """Parse the deliberate-exclusion list."""
    frame = pd.read_csv(path, dtype="string")
    return frame[["ticker", "company_name", "exclusion_class", "exclusion_reason"]]


def read_membership(path: Path) -> pd.DataFrame:
    """Parse the index membership intervals."""
    frame = pd.read_csv(path)
    frame = frame.rename(columns={"ticker": "ticker"})
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce").dt.date
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.date

    # A row without a start date cannot define an interval; there is nothing
    # useful to do with it downstream.
    before = len(frame)
    frame = frame.dropna(subset=["start_date"])
    if len(frame) < before:
        logger.warning("Dropped %d membership row(s) with no start_date", before - len(frame))

    return frame[["ticker", "start_date", "end_date"]]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def copy_frame(frame: pd.DataFrame, table: str, columns: list[str]) -> int:
    """Replace a table's contents with a frame, via ``COPY ... FROM STDIN``.

    The frame is serialised to an in-memory CSV buffer and streamed in one
    round trip. Empty strings are declared as NULL so that nullable columns
    (``end_date``, missing OHLCV values) land as NULL rather than as text.

    The TRUNCATE and the COPY share one transaction, so a failed load leaves
    the previous contents intact rather than an empty table.

    Returns:
        Number of rows loaded.
    """
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, header=False, columns=columns, na_rep="")
    buffer.seek(0)

    column_list = ", ".join(f'"{c}"' for c in columns)
    copy_sql = f"COPY {table} ({column_list}) FROM STDIN WITH (FORMAT csv, NULL '')"

    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table}")
        cur.copy_expert(copy_sql, buffer)

    logger.info("Loaded %s rows into %s", f"{len(frame):,}", table)
    return len(frame)


def ingest(skip_prices: bool = False, recreate: bool = False) -> dict[str, int]:
    """Run the full Bronze-layer load.

    Args:
        skip_prices: Load only the small reference tables, leaving
            ``bronze.daily_prices`` untouched. Useful while iterating on
            reference logic without re-copying 1.22M rows.
        recreate: Drop every Bronze table first. Needed only after a schema
            change, since the normal path is idempotent.

    Returns:
        Mapping of table name to rows loaded.
    """
    settings = get_settings()
    settings.paths.ensure()
    loaded: dict[str, int] = {}

    started = time.perf_counter()

    logger.info("Creating Bronze schema objects")
    run_script(settings.paths.sql / "bronze" / "01_create_schemas.sql")
    if recreate:
        logger.warning("--recreate: dropping all Bronze tables")
        run_script(settings.paths.sql / "bronze" / "00_drop_bronze.sql")
    run_script(settings.paths.sql / "bronze" / "02_create_bronze_tables.sql")

    snapshot_path = settings.paths.raw_reference / "sp500_current_snapshot.csv"
    membership_path = settings.paths.raw_reference / "sp500_ticker_start_end.csv"

    loaded["bronze.sp500_current_snapshot"] = copy_frame(
        read_current_snapshot(snapshot_path),
        "bronze.sp500_current_snapshot",
        [
            "ticker",
            "security_name",
            "gics_sector",
            "gics_sub_industry",
            "headquarters",
            "date_added",
            "cik",
            "founded",
        ],
    )

    loaded["bronze.sp500_membership"] = copy_frame(
        read_membership(membership_path),
        "bronze.sp500_membership",
        ["ticker", "start_date", "end_date"],
    )

    seeds_dir = settings.paths.dbt_project / "seeds"

    loaded["bronze.gics_sector_registry"] = copy_frame(
        read_sector_registry(seeds_dir / "gics_sector_registry.csv"),
        "bronze.gics_sector_registry",
        ["gics_sector", "existed_from", "existed_to", "source_id", "notes"],
    )

    loaded["bronze.excluded_entities"] = copy_frame(
        read_excluded_entities(seeds_dir / "excluded_entities.csv"),
        "bronze.excluded_entities",
        ["ticker", "company_name", "exclusion_class", "exclusion_reason"],
    )

    seed_path = seeds_dir / "sector_history.csv"
    loaded["bronze.sector_history"] = copy_frame(
        read_sector_history(seed_path),
        "bronze.sector_history",
        [
            "ticker",
            "company_name",
            "change_type",
            "old_gics_sector",
            "new_gics_sector",
            "old_gics_sub_industry",
            "new_gics_sub_industry",
            "effective_after_close",
            "first_trading_day",
            "source_id",
        ],
    )

    if skip_prices:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze.daily_prices")
            existing = cur.fetchone()[0]
        logger.info(
            "--skip-prices set; bronze.daily_prices left untouched (%s rows)",
            f"{existing:,}",
        )
    else:
        prices = read_all_prices(settings.paths.raw_prices)
        loaded["bronze.daily_prices"] = copy_frame(prices, "bronze.daily_prices", _PRICE_COLUMNS)

    # ANALYZE now rather than waiting for autovacuum: the performance
    # benchmarks compare query plans, and a plan chosen from stale statistics
    # would make the before/after comparison meaningless.
    with connect(autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("ANALYZE bronze.daily_prices")
        cur.execute("ANALYZE bronze.sp500_current_snapshot")
        cur.execute("ANALYZE bronze.sp500_membership")
        cur.execute("ANALYZE bronze.sector_history")
        cur.execute("ANALYZE bronze.gics_sector_registry")
        cur.execute("ANALYZE bronze.excluded_entities")

    logger.info("Bronze ingestion finished in %.1fs", time.perf_counter() - started)
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load raw sources into the Bronze layer.")
    parser.add_argument(
        "--skip-prices",
        action="store_true",
        help="Load only the reference tables, leaving bronze.daily_prices untouched.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop every Bronze table before loading. Needed only after a schema change.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        loaded = ingest(skip_prices=args.skip_prices, recreate=args.recreate)
    except IngestionError as exc:
        logger.error("Ingestion failed: %s", exc)
        return 1

    print("\nBronze layer loaded:")
    for table, rows in loaded.items():
        print(f"  {table:<36} {rows:>10,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
