"""Tests for pit_lab.ingest — the CSV-parsing logic, independent of a live
database. No test in this file touches PostgreSQL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pit_lab.ingest import (
    IngestionError,
    read_price_file,
    read_sector_history,
)


@pytest.fixture
def price_csv(tmp_path: Path) -> Path:
    """A minimal file matching the real Kaggle export's 3-row header quirk."""
    content = (
        "Price,Close,High,Low,Open,Volume\n"
        "Ticker,TEST,TEST,TEST,TEST,TEST\n"
        "Date,,,,,\n"
        "2020-01-02,100.0,101.0,99.0,100.5,1000\n"
        "2020-01-03,102.0,103.0,101.0,101.5,1100\n"
    )
    path = tmp_path / "TEST.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_read_price_file_uses_filename_as_ticker(price_csv: Path):
    frame = read_price_file(price_csv)
    assert (frame["ticker"] == "TEST").all()


def test_read_price_file_column_shape(price_csv: Path):
    frame = read_price_file(price_csv)
    assert list(frame.columns) == [
        "ticker",
        "trade_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]
    assert len(frame) == 2


def test_read_price_file_parses_dates(price_csv: Path):
    frame = read_price_file(price_csv)
    assert frame["trade_date"].iloc[0].isoformat() == "2020-01-02"


def test_read_price_file_missing_columns_raises(tmp_path: Path):
    bad = tmp_path / "BAD.csv"
    bad.write_text("Price,Close\nTicker,BAD\nDate,\n2020-01-02,100.0\n", encoding="utf-8")
    with pytest.raises(IngestionError, match="missing expected columns"):
        read_price_file(bad)


@pytest.fixture
def sector_history_csv(tmp_path: Path) -> Path:
    content = (
        "ticker,company_name,change_type,old_gics_sector,new_gics_sector,"
        "old_gics_sub_industry,new_gics_sub_industry,effective_after_close,"
        "first_trading_day,source_id\n"
        "GOOGL,Alphabet,reclassification,Information Technology,"
        "Communication Services,,,2018-09-21,2018-09-24,S1\n"
    )
    path = tmp_path / "sector_history.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_read_sector_history_parses_dates(sector_history_csv: Path):
    frame = read_sector_history(sector_history_csv)
    assert frame["effective_after_close"].iloc[0].isoformat() == "2018-09-21"
    assert frame["first_trading_day"].iloc[0].isoformat() == "2018-09-24"


def test_read_sector_history_rejects_identical_old_and_new_sector(tmp_path: Path):
    content = (
        "ticker,company_name,change_type,old_gics_sector,new_gics_sector,"
        "old_gics_sub_industry,new_gics_sub_industry,effective_after_close,"
        "first_trading_day,source_id\n"
        "XYZ,Example Corp,reclassification,Financials,Financials,,,"
        "2020-01-01,2020-01-02,S1\n"
    )
    path = tmp_path / "bad_seed.csv"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(IngestionError, match="identical old/new sector"):
        read_sector_history(path)


def test_actual_seed_file_has_no_identical_sector_rows():
    """Guards the real seed committed to the repo, not just a fixture."""
    repo_root = Path(__file__).resolve().parents[1]
    seed_path = repo_root / "dbt_pit" / "seeds" / "sector_history.csv"
    frame = read_sector_history(seed_path)  # raises IngestionError if any row is bad
    assert len(frame) > 0


def test_actual_seed_file_dates_are_ordered_correctly():
    """first_trading_day must always be after effective_after_close - the
    off-by-one convention documented in docs/sector_sources.md section 5."""
    repo_root = Path(__file__).resolve().parents[1]
    seed_path = repo_root / "dbt_pit" / "seeds" / "sector_history.csv"
    frame = read_sector_history(seed_path)
    assert (frame["first_trading_day"] > frame["effective_after_close"]).all()
