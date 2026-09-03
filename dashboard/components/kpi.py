"""Stat-tile / KPI row component.

Per the project's dataviz standard: a single headline number is a stat tile,
not a one-bar bar chart. This is the one reusable building block for that
pattern, used on every page that has a headline metric to lead with.
"""

from __future__ import annotations

import streamlit as st


def stat_tile(value: str, label: str, tone: str = "") -> str:
    """Render one stat tile as an HTML fragment.

    Args:
        value: The headline figure, already formatted (e.g. "554.1%").
        label: One short line describing what the figure is.
        tone: "" | "critical" | "good" | "accent" — colors the value only,
            following the fixed status-color assignment in theme/colors.py.
    """
    tone_class = f" {tone}" if tone else ""
    return f"""
        <div class="pit-stat">
            <div class="v{tone_class}">{value}</div>
            <div class="l">{label}</div>
        </div>
    """


def kpi_row(items: list[tuple[str, str, str]]) -> None:
    """Render a row of stat tiles.

    Args:
        items: list of (value, label, tone) tuples, one per tile.
    """
    cols = st.columns(len(items))
    for col, (value, label, tone) in zip(cols, items, strict=True):
        with col:
            st.markdown(stat_tile(value, label, tone), unsafe_allow_html=True)
