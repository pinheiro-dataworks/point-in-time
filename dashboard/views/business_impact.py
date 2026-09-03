"""07 - Business Impact: the value proposition, in the terms a stakeholder uses."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.components.data import load_anchor_metric


def _date(value) -> str:
    """Format a date-ish value as YYYY-MM-DD, stripping any time component."""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def render() -> None:
    st.markdown('<div class="pit-eyebrow">07 · Business Impact</div>', unsafe_allow_html=True)
    st.header("What this is actually worth")
    st.markdown(
        '<p class="pit-lede">Point-in-time correctness is not a data-modeling '
        "nicety — it is a control against three concrete, costed risks. Each "
        "is stated in the language the relevant stakeholder actually uses.</p>",
        unsafe_allow_html=True,
    )

    anchor = load_anchor_metric()
    worst = (
        anchor.dropna(subset=["abs_difference_pp"])
        .sort_values("abs_difference_pp", ascending=False)
        .iloc[0]
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="pit-card" style="border-color:#D4A657;background:rgba(212,166,87,0.06);">
<b>The anchor metric.</b><br><br>
Recalculating cumulative sector returns for <b>{worst["gics_sector"]}</b>,
{_date(worst["comparison_start"])} to {_date(anchor["analysis_end"].iloc[0])}, using each
stock's GICS sector <i>as classified on the trade date</i> instead of today's
classification, changed the reported return by
<b>{worst["difference_pp"]:+.1f} percentage points</b> and reassigned
<b>{int(worst["reclassified_tickers"])}</b> companies' historical performance —
<b>{int(worst["misattributed_observations"]):,}</b> individual return
observations filed under the wrong sector by a naive join.
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
<div class="pit-card">
<span class="pit-badge">Financial / audit</span><br><br>
Misstatement risk in sector-return figures that feed factsheets, ETF marketing
material, and performance-attribution reports. A sector factsheet built on
today's classification silently overstates or understates the return an
investor actually would have earned holding that sector through the period —
a number that never existed on any given day.
</div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
<div class="pit-card">
<span class="pit-badge">Regulatory</span><br><br>
SEC / FINRA disclosure integrity for sector-based investment products is a
live compliance concern, not an invented analogy. A fund whose "Technology
sector return since 2016" figure silently includes years of Visa and
Mastercard performance the sector never actually held is a disclosure problem
the moment a regulator checks the trade-date classification against the label
in the marketing material.
</div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
<div class="pit-card">
<span class="pit-badge">ML / leakage</span><br><br>
Training a sector-classification or sector-momentum model on backfilled
labels is target leakage — the model learns from a label that did not exist
on the date it is predicting. This is the same mechanism a temporal
anti-leakage validator exists to catch downstream; this project builds the
data layer that makes that kind of validation possible upstream, before a
model ever sees the data.
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Who this is for")
    st.markdown(
        """
- **A quant researcher** backtesting a sector-rotation strategy, who needs
  returns joined to the sector that was actually tradeable knowledge on the
  trade date — not a lookback advantage no trader ever had.
- **A data platform team** building the dimensional layer underneath
  sector-based reporting, who needs a reference implementation of SCD Type 2
  that is provably correct (see the Data Quality page) rather than assumed
  correct.
- **An ML engineer** validating that a model's training data has no temporal
  leakage, who needs a concrete example of what backfilled-label leakage
  looks like with real dates attached, not a synthetic toy case.
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
