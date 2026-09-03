"""Tests for dashboard.components.charts — pure figure-building functions.

No Streamlit runtime needed: these functions take a DataFrame and return a
Plotly Figure, so they're tested directly.
"""

from __future__ import annotations

import pandas as pd
import pytest
from dashboard.components.charts import diverging_bar_chart, paired_bar_chart


@pytest.fixture
def anchor_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gics_sector": ["Information Technology", "Communication Services", "Energy"],
            "difference_pp": [78.2, -0.0, None],
            "abs_difference_pp": [78.2, 0.0, None],
            "naive_cumulative_return": [812.1, 153.5, 175.3],
            "pit_cumulative_return": [733.9, 153.5, 175.3],
        }
    )


def test_diverging_bar_chart_drops_null_rows(anchor_df: pd.DataFrame):
    fig = diverging_bar_chart(anchor_df)
    # Energy has a null difference_pp and must not appear as a bar.
    plotted_sectors = list(fig.data[0].y)
    assert "Energy" not in plotted_sectors
    assert "Information Technology" in plotted_sectors


def test_diverging_bar_chart_x_range_has_headroom_for_labels(anchor_df: pd.DataFrame):
    fig = diverging_bar_chart(anchor_df)
    x_range = fig.layout.xaxis.range
    max_value = anchor_df["difference_pp"].max()
    # The outside data-label needs room past the longest bar or it clips
    # against the plot edge - this is the exact bug fixed during QA.
    assert x_range[1] > max_value


def test_diverging_bar_chart_sign_determines_color(anchor_df: pd.DataFrame):
    from dashboard.theme import colors

    fig = diverging_bar_chart(anchor_df)
    bar_colors = list(fig.data[0].marker.color)
    sectors = list(fig.data[0].y)
    it_index = sectors.index("Information Technology")
    assert bar_colors[it_index] == colors.DIVERGING_POSITIVE


def test_paired_bar_chart_filters_to_requested_sectors(anchor_df: pd.DataFrame):
    fig = paired_bar_chart(anchor_df, ["Information Technology", "Energy"])
    naive_trace = fig.data[0]
    assert set(naive_trace.x) == {"Information Technology", "Energy"}
    assert "Communication Services" not in list(naive_trace.x)


def test_paired_bar_chart_uses_status_colors(anchor_df: pd.DataFrame):
    from dashboard.theme import colors

    fig = paired_bar_chart(anchor_df, ["Information Technology"])
    naive_trace, pit_trace = fig.data
    assert naive_trace.marker.color == colors.NAIVE_COLOR
    assert pit_trace.marker.color == colors.PIT_COLOR
