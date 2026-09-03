"""Cached Parquet loading for the dashboard.

The dashboard never touches PostgreSQL. It reads the Gold-layer artefacts
written by ``python -m pit_lab.export`` from ``data/processed/`` — see that
module's docstring for why. DuckDB reads Parquet directly with no separate
load step, and pandas gives Streamlit's caching and charting layers a frame
they already know how to work with.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

# dashboard/components/data.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def _read_parquet(filename: str) -> pd.DataFrame:
    path = PROCESSED_DIR / filename
    if not path.exists():
        st.error(
            f"Missing data file: `{filename}`. Run "
            "`python -m pit_lab.export` to regenerate data/processed/ from "
            "the warehouse before launching the dashboard."
        )
        st.stop()
    return duckdb.sql(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()


@st.cache_data(show_spinner=False)
def load_anchor_metric() -> pd.DataFrame:
    """One row per sector: the naive-vs-point-in-time headline comparison."""
    return _read_parquet("anchor_metric.parquet")


@st.cache_data(show_spinner=False)
def load_cumulative_returns() -> pd.DataFrame:
    """Daily cumulative return series, both join bases, every sector."""
    df = _read_parquet("sector_cumulative_returns.parquet")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


@st.cache_data(show_spinner=False)
def load_daily_returns() -> pd.DataFrame:
    """Daily equal-weighted sector return, both join bases."""
    df = _read_parquet("sector_daily_returns.parquet")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


@st.cache_data(show_spinner=False)
def load_dimension() -> pd.DataFrame:
    """The SCD Type 2 sector dimension - every version, every ticker."""
    df = _read_parquet("dim_sector_scd.parquet")
    df["valid_from"] = pd.to_datetime(df["valid_from"])
    df["valid_to"] = pd.to_datetime(df["valid_to"])
    return df


@st.cache_data(show_spinner=False)
def load_ticker_universe() -> pd.DataFrame:
    """The analysable ticker set."""
    return _read_parquet("ticker_universe.parquet")


@st.cache_data(show_spinner=False)
def load_excluded_tickers() -> pd.DataFrame:
    """Every ticker held out of the universe, with a reason."""
    return _read_parquet("excluded_tickers.parquet")


@st.cache_data(show_spinner=False)
def load_benchmarks() -> dict:
    """Query-performance benchmark results, written by pit_lab.benchmark."""
    import json

    path = PROCESSED_DIR / "benchmarks.json"
    if not path.exists():
        return {"results": []}
    return json.loads(path.read_text(encoding="utf-8"))


def data_freshness() -> str | None:
    """Modification time of the anchor metric file, for a 'data as of' caption."""
    path = PROCESSED_DIR / "anchor_metric.parquet"
    if not path.exists():
        return None
    import datetime as dt

    return dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
