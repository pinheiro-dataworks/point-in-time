"""Warehouse build orchestration.

Runs the Silver and Gold SQL scripts in dependency order and reports per-stage
timings. Scripts are discovered by their numeric filename prefix rather than
listed here, so adding a step is a matter of dropping a correctly-named file
into ``sql/<layer>/`` — the ordering contract lives in the filenames, where it
is visible when browsing the directory.

Run as a module::

    python -m pit_lab.build              # Silver + Gold
    python -m pit_lab.build --layer gold # Gold only
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from pit_lab.config import get_settings
from pit_lab.db import connect, fetch_all, fetch_one, run_script

logger = logging.getLogger(__name__)

LAYERS = ("silver", "gold")


def discover_scripts(layer_dir: Path) -> list[Path]:
    """Return a layer's ``.sql`` files in numeric-prefix order.

    Sorting is on the filename, and the ``NN_`` prefix convention makes that
    lexicographic sort match the intended execution order.
    """
    scripts = sorted(layer_dir.glob("[0-9][0-9]_*.sql"))
    if not scripts:
        raise FileNotFoundError(f"No numbered SQL scripts found in {layer_dir}")
    return scripts


def set_analysis_window() -> None:
    """Push the configured reporting window into ``silver.analysis_window``.

    Done from Python because the window comes from the environment, and done
    with a bound parameter rather than string interpolation so the dates cannot
    be injected into the statement.
    """
    settings = get_settings()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE silver.analysis_window")
        cur.execute(
            "INSERT INTO silver.analysis_window (singleton, start_date, end_date) "
            "VALUES (TRUE, %s, %s)",
            (settings.window.start, settings.window.end),
        )
    logger.info("Analysis window set: %s to %s", settings.window.start, settings.window.end)


def build_layer(layer: str) -> dict[str, float]:
    """Execute every script in a layer, returning per-script durations."""
    settings = get_settings()
    layer_dir = settings.paths.sql / layer
    timings: dict[str, float] = {}

    logger.info("--- Building %s layer ---", layer)
    for script in discover_scripts(layer_dir):
        timings[f"{layer}/{script.name}"] = run_script(script)
        # The window table is created by the Silver DDL and read by everything
        # downstream, so it has to be populated the moment it exists.
        if layer == "silver" and script.name.startswith("01_"):
            set_analysis_window()

    return timings


def summarise() -> None:
    """Print row counts and the headline result after a build."""
    tables = [
        "silver.ticker_universe",
        "silver.excluded_tickers",
        "silver.stg_sector_events",
        "silver.dim_sector_scd",
        "silver.dim_reconciliation",
        "silver.sector_existence_violations",
        "silver.fact_returns",
        "gold.fact_returns_pit",
        "gold.sector_daily_returns",
        "gold.sector_cumulative_returns",
        "gold.anchor_metric",
    ]

    print("\nWarehouse contents")
    print("-" * 58)
    for table in tables:
        row = fetch_one(f"SELECT COUNT(*) AS n FROM {table}")
        count = row["n"] if row else 0
        print(f"  {table:<34} {count:>12,}")

    for table, message in (
        ("silver.dim_reconciliation", "failed SCD2 reconciliation"),
        ("silver.sector_existence_violations", "claim a sector before it existed"),
    ):
        row = fetch_one(f"SELECT COUNT(*) AS n FROM {table}")
        if row and row["n"]:
            logger.warning("%d row(s) %s - inspect %s", row["n"], message, table)

    print("\nAnchor metric - naive vs point-in-time, compounded over the COMMON period")
    print("-" * 100)
    print(
        f"  {'Sector':<26}{'From':>12}{'Naive %':>11}{'PIT %':>11}"
        f"{'Diff pp':>10}{'Tickers':>9}{'Misattr. obs':>15}"
    )
    print("-" * 100)

    rows = fetch_all(
        """
        SELECT gics_sector, comparison_start, naive_cumulative_return,
               pit_cumulative_return, difference_pp, reclassified_tickers,
               misattributed_observations
        FROM gold.anchor_metric
        ORDER BY abs_difference_pp DESC NULLS LAST
        """
    )

    def fmt(value: float | None, width: int) -> str:
        return f"{'n/a':>{width}}" if value is None else f"{value:>{width}.1f}"

    for row in rows:
        print(
            f"  {row['gics_sector']:<26}"
            f"{row['comparison_start']!s:>12}"
            f"{fmt(row['naive_cumulative_return'], 11)}"
            f"{fmt(row['pit_cumulative_return'], 11)}"
            f"{fmt(row['difference_pp'], 10)}"
            f"{row['reclassified_tickers']:>9}"
            f"{row['misattributed_observations']:>15,}"
        )

    # The full-window naive figure is a separate finding from the join error,
    # so it is reported separately rather than folded into the table above.
    absent = fetch_all(
        """
        SELECT gics_sector, sector_existed_from, pct_period_sector_absent,
               naive_full_window_return, naive_cumulative_return
        FROM gold.anchor_metric
        WHERE pct_period_sector_absent > 0
        ORDER BY pct_period_sector_absent DESC
        """
    )
    if absent:
        print("\nSectors credited with returns from before they existed")
        print("-" * 100)
        for row in absent:
            print(
                f"  {row['gics_sector']:<26}"
                f"created {row['sector_existed_from']}, "
                f"absent for {row['pct_period_sector_absent']:.1f}% of the window; "
                f"a naive report publishes "
                f"{fmt(row['naive_full_window_return'], 0).strip()}% "
                f"vs {fmt(row['naive_cumulative_return'], 0).strip()}% like-for-like"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Silver and Gold layers.")
    parser.add_argument(
        "--layer",
        choices=LAYERS,
        help="Build only one layer. Default: both, in order.",
    )
    parser.add_argument("--no-summary", action="store_true", help="Skip the post-build report.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    layers = (args.layer,) if args.layer else LAYERS

    started = time.perf_counter()
    timings: dict[str, float] = {}
    for layer in layers:
        timings.update(build_layer(layer))
    total = time.perf_counter() - started

    print("\nBuild timings")
    print("-" * 58)
    for name, seconds in timings.items():
        print(f"  {name:<44} {seconds:>7.2f}s")
    print(f"  {'TOTAL':<44} {total:>7.2f}s")

    if not args.no_summary:
        summarise()

    return 0


if __name__ == "__main__":
    sys.exit(main())
