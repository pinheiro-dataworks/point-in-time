"""02 - Architecture: Bronze -> Silver -> Gold -> Serving."""

from __future__ import annotations

import streamlit as st

from dashboard.components.data import load_dimension, load_excluded_tickers, load_ticker_universe


def render() -> None:
    st.markdown('<div class="pit-eyebrow">02 · Architecture</div>', unsafe_allow_html=True)
    st.header("Bronze → Silver → Gold → Serving")
    st.markdown(
        '<p class="pit-lede">No Airflow, on purpose — this project stays '
        "SQL-first. Orchestration runs through a scheduled GitHub Actions job "
        "(<code>dbt build &amp;&amp; dbt test</code>).</p>",
        unsafe_allow_html=True,
    )

    universe = load_ticker_universe()
    dim = load_dimension()
    excluded = load_excluded_tickers()

    with st.expander("🟫 BRONZE — Raw ingestion", expanded=True):
        st.markdown(
            """
Four source tables, landed as-is via `python -m pit_lab.ingest`, no
transformation beyond typing.

- **`daily_prices`** — OHLCV per ticker, 2015-12-21 to 2025-12-19 (Kaggle)
- **`sp500_current_snapshot`** — current GICS Sector / Sub-Industry per ticker (fja05680/sp500)
- **`sector_history`** — the curated, sourced reclassification seed (this project's own research)
- **`gics_sector_registry`** — when each GICS sector label was in force
            """
        )

    with st.expander("⬜ SILVER — SCD assembly", expanded=True):
        st.markdown(
            f"""
Where the point-in-time dimension actually gets built, in
`sql/silver/03_build_dim_sector_scd.sql` — a hand-rolled UPDATE/INSERT cycle,
no ORM, no macro hiding the mechanism.

- **`ticker_universe`** — {len(universe):,} tickers with both price history and a current sector
- **`dim_sector_scd`** — {len(dim):,} dimension rows ({int((dim["version_number"] > 1).sum())} are second-or-later versions)
- **`excluded_tickers`** — {len(excluded)} tickers held out, each with a recorded reason
- **`fact_returns`** — daily returns via `LAG`, one row per ticker per trading day
            """
        )

    with st.expander("🟨 GOLD — Point-in-time correct", expanded=True):
        st.markdown(
            """
Range join on trade date, plus the naive comparison, in one pass.

- **`fact_returns_pit`** — every return, joined to BOTH the sector valid on the
  trade date and the sector the ticker carries today
- **`sector_daily_returns` / `sector_cumulative_returns`** — equal-weighted
  sector index, both join bases
- **`anchor_metric`** — the headline naive-vs-correct comparison, rebased onto
  the common period both series can be compared over — see **Gold Dashboard**
            """
        )

    with st.expander("🟩 SERVING — This dashboard", expanded=True):
        st.markdown(
            """
This Streamlit app, deployed on Streamlit Community Cloud at $0/month. It does
not connect to PostgreSQL — it reads Parquet files exported from the Gold
layer by `python -m pit_lab.export`, via DuckDB, so the deployed app has no
database dependency at all.
            """
        )

    st.markdown(
        """
        <div class="pit-footer-note">
        Point-in-Time Analytics Lab · <a href="https://github.com/pinheiro-dataworks" target="_blank">Renan Pinheiro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
