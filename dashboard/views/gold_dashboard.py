"""04 - Gold Dashboard: the interactive naive-vs-point-in-time comparison.

This is the page the project's headline result lives on. Three charts, each
chosen by the job the data does (see components/charts.py's module docstring),
all driven by the same gold.anchor_metric / gold.sector_cumulative_returns
tables the warehouse actually produced — nothing here is illustrative.
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.charts import diverging_bar_chart, emphasis_line_chart, paired_bar_chart
from dashboard.components.data import data_freshness, load_anchor_metric, load_cumulative_returns
from dashboard.components.kpi import kpi_row


def render() -> None:
    st.markdown('<div class="pit-eyebrow">04 · Gold Dashboard</div>', unsafe_allow_html=True)
    st.header("Naive vs. point-in-time correct")
    st.markdown(
        '<p class="pit-lede">Same price history, two different sector joins. '
        "Every figure below is computed from the warehouse — nothing is "
        "illustrative.</p>",
        unsafe_allow_html=True,
    )

    freshness = data_freshness()
    if freshness:
        st.caption(f"Warehouse snapshot exported {freshness}")

    anchor = load_anchor_metric()
    cum = load_cumulative_returns()

    # --- headline KPIs, from the sector with the largest naive-vs-PIT gap ---
    worst = (
        anchor.dropna(subset=["abs_difference_pp"])
        .sort_values("abs_difference_pp", ascending=False)
        .iloc[0]
    )
    total_misattributed = int(anchor["misattributed_observations"].sum())
    total_reclassified = int(anchor["reclassified_tickers"].sum())

    kpi_row(
        [
            (worst["gics_sector"], "Sector with the largest naive-vs-correct gap", "accent"),
            (
                f"{worst['difference_pp']:+.1f} pp",
                "Naive minus point-in-time, common period",
                "critical",
            ),
            (f"{total_reclassified}", "Ticker-sector moves reflected in the dimension", ""),
            (
                f"{total_misattributed:,}",
                "Observations a naive join files under the wrong sector",
                "critical",
            ),
        ]
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------
    # Diverging bar: the anchor metric itself
    # -------------------------------------------------------------------
    st.subheader("The anchor metric — naive minus point-in-time, every sector")
    st.caption(
        "Compounded over the period both series can be compared over "
        "(a sector created mid-window cannot be compared before it existed — "
        "see the Methodology page). Positive = naive OVERSTATES the sector's "
        "return; negative = naive UNDERSTATES it."
    )
    st.plotly_chart(diverging_bar_chart(anchor), width="stretch", config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------
    # Emphasis line: pick a sector, see its two series diverge
    # -------------------------------------------------------------------
    st.subheader("Cumulative return by sector — pick one to compare bases")
    sectors = sorted(cum["gics_sector"].unique().tolist())
    default_idx = sectors.index(worst["gics_sector"]) if worst["gics_sector"] in sectors else 0
    picked = st.selectbox(
        "Sector",
        sectors,
        index=default_idx,
        label_visibility="collapsed",
        key="gold_dashboard_sector_pick",
    )

    basis_col1, basis_col2 = st.columns(2)
    with basis_col1:
        st.markdown("**Naive — today's sector, applied to all history**")
        naive_df = cum[cum["join_basis"] == "naive"]
        st.plotly_chart(
            emphasis_line_chart(naive_df, picked),
            width="stretch",
            config={"displayModeBar": False},
        )
    with basis_col2:
        st.markdown("**Point-in-time — sector valid on the trade date**")
        pit_df = cum[cum["join_basis"] == "point_in_time"]
        st.plotly_chart(
            emphasis_line_chart(pit_df, picked),
            width="stretch",
            config={"displayModeBar": False},
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------
    # Paired bar: naive vs PIT, status-colored, for the top movers
    # -------------------------------------------------------------------
    st.subheader("Naive vs. point-in-time, side by side")
    top_sectors = (
        anchor.dropna(subset=["abs_difference_pp"])
        .sort_values("abs_difference_pp", ascending=False)
        .head(6)["gics_sector"]
        .tolist()
    )
    st.plotly_chart(
        paired_bar_chart(anchor, top_sectors), width="stretch", config={"displayModeBar": False}
    )

    with st.expander("View the underlying anchor_metric table"):
        display_cols = [
            "gics_sector",
            "comparison_start",
            "naive_cumulative_return",
            "pit_cumulative_return",
            "difference_pp",
            "reclassified_tickers",
            "misattributed_observations",
            "pct_period_sector_absent",
        ]
        ordered = anchor.sort_values("abs_difference_pp", ascending=False, na_position="last")
        st.dataframe(
            ordered[display_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "comparison_start": st.column_config.DateColumn(
                    "comparison_start", format="YYYY-MM-DD"
                ),
                "naive_cumulative_return": st.column_config.NumberColumn(
                    "naive_cumulative_return", format="%.1f%%"
                ),
                "pit_cumulative_return": st.column_config.NumberColumn(
                    "pit_cumulative_return", format="%.1f%%"
                ),
                "difference_pp": st.column_config.NumberColumn("difference_pp", format="%+.1f"),
                "pct_period_sector_absent": st.column_config.NumberColumn(
                    "pct_period_sector_absent", format="%.1f%%"
                ),
            },
        )

    st.markdown(
        """
        <div class="pit-footer-note">
        Point-in-Time Analytics Lab · <a href="https://github.com/pinheiro-dataworks" target="_blank">Renan Pinheiro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
