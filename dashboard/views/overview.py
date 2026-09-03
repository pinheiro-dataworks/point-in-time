"""01 - Overview: the business problem, stated plainly, with real numbers."""

from __future__ import annotations

import streamlit as st

from dashboard.components.data import load_anchor_metric
from dashboard.components.kpi import kpi_row


def render() -> None:
    st.markdown('<div class="pit-eyebrow">01 · Overview</div>', unsafe_allow_html=True)
    st.title("Naive joins silently corrupt historical analytics.")
    st.markdown(
        '<p class="pit-lede">This project proves it with a real, dated GICS '
        "sector reclassification — and fixes it with proper SCD Type 2 "
        "modeling.</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
On September 21, 2018, S&P Dow Jones Indices and MSCI created a new GICS
sector, **Communication Services**, and reassigned companies like Alphabet,
Meta, and Netflix out of Technology and Consumer Discretionary. On March 17,
2023, Visa, Mastercard, and PayPal moved from Technology to Financials. Any
report or backtest that joins historical returns to a company's *current*
sector — instead of the sector in effect on the trade date — is quietly
rewriting history for every year that gap existed.

That's not an invented business rule. It's a real, externally-verifiable
classification-committee decision with a public paper trail — which makes it a
cleaner point-in-time correctness case study than most. Every source backing
this project's sector-history table is listed and dated on the **Methodology**
page.
        """
    )

    anchor = load_anchor_metric()
    reclassified_total = int(anchor["reclassified_tickers"].sum())
    misattributed_total = int(anchor["misattributed_observations"].sum())
    worst_row = (
        anchor.dropna(subset=["abs_difference_pp"])
        .sort_values("abs_difference_pp", ascending=False)
        .iloc[0]
    )

    st.markdown("<br>", unsafe_allow_html=True)
    kpi_row(
        [
            ("2", "Real, dated GICS reclassification events used as SCD2 seed data", "accent"),
            (f"{reclassified_total}", "Ticker-sector moves reflected in the dimension", ""),
            (
                f"{misattributed_total:,}",
                "Return observations a naive join files under the wrong sector",
                "critical",
            ),
            (
                f"{worst_row['difference_pp']:+.1f} pp",
                f"Largest naive-vs-correct gap — {worst_row['gics_sector']}",
                "critical" if abs(worst_row["difference_pp"]) > 5 else "good",
            ),
        ]
    )

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(
            """
<div class="pit-card">
<b>What actually happened.</b> GOOGL, TWTR, ATVI, EA and TTWO (from Information
Technology) and META, NFLX, LYV (from Consumer Discretionary) moved into the
newly created Communication Services sector on 2018-09-24. AT&amp;T and Verizon's
sector was renamed underneath them, unmoved. V, MA, PYPL, FIS, FISV, GPN and
JKHY moved from Information Technology to Financials on 2023-03-20, alongside
ADP, PAYX and BR moving to Industrials and TGT, DG, DLTR moving to Consumer
Staples. A naive join reports every historical trade for these tickers under
today's sector — silently rewriting years of sector-level performance history.
</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
<div class="pit-card">
<b>Why this matters beyond the demo.</b><br><br>
"Point-in-time" and "look-ahead bias" are literal terms used in institutional
finance to prevent backtests from cheating on data that did not exist yet on
the trade date. A sector-classification model trained on historical prices
joined to today's sector labels has textbook target leakage — the same
category of error a temporal anti-leakage validator is built to catch. This
project builds the data layer that makes that kind of validation possible in
the first place.
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="pit-footer-note">
        Point-in-Time Analytics Lab — S&amp;P 500 / GICS edition · built by
        <a href="https://github.com/pinheiro-dataworks" target="_blank">Renan Pinheiro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
