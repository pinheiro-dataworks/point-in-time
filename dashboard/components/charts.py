"""Reusable Plotly figure builders.

Three chart forms cover every visualisation in this dashboard, chosen by the
data's job rather than by what looked available:

* **Emphasis line** - the 11-sector cumulative-return series. Eleven series is
  too many for categorical color (the palette's series-count ladder caps
  useful categorical identity around 7-8); the actual story is "how does one
  sector's naive series diverge from its point-in-time series," so one sector
  is highlighted and the rest recede to a single de-emphasis gray.
* **Diverging bar** - the anchor metric's signed difference_pp. Positive means
  naive overstates the sector's return, negative means it understates it -
  textbook polarity, so it gets the diverging pair, not a categorical one.
* **Paired bar** - naive vs. point-in-time, side by side, for a shortlist of
  sectors. This is the one place the reserved status pair (good/critical)
  appears, because it is literally encoding "correct" vs. "wrong."

Every figure sets hairline gridlines, a transparent background (so Streamlit's
cream page shows through), and a unified hovermode - the hover layer is not
optional per the project's dataviz standard.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import colors

_FONT = {"family": "-apple-system, Segoe UI, sans-serif", "color": colors.INK_SECONDARY, "size": 12}


def _base_layout(**overrides) -> dict:
    layout = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": _FONT,
        "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
        "hovermode": "x unified",
        "hoverlabel": {
            "bgcolor": colors.CHART_SURFACE,
            "bordercolor": colors.BASELINE,
            "font": {"family": _FONT["family"], "color": colors.INK_PRIMARY, "size": 12},
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11.5, "color": colors.INK_SECONDARY},
        },
    }
    layout.update(overrides)
    return layout


def _axis(title: str = "", tickformat: str | None = None) -> dict:
    return {
        "title": {"text": title, "font": {"size": 11.5, "color": colors.INK_MUTED}},
        "showgrid": True,
        "gridcolor": colors.GRIDLINE,
        "gridwidth": 1,
        "griddash": "solid",
        "zeroline": False,
        "showline": True,
        "linecolor": colors.BASELINE,
        "tickfont": {"size": 11, "color": colors.INK_MUTED},
        "tickformat": tickformat,
    }


def emphasis_line_chart(
    df: pd.DataFrame,
    highlighted_sector: str,
    value_col: str = "cumulative_return",
    x_col: str = "trade_date",
    group_col: str = "gics_sector",
) -> go.Figure:
    """Eleven-series line chart with one sector in the accent hue, rest gray.

    ``df`` must already be filtered to a single join_basis - this function
    draws exactly one line per sector, not one per (sector, basis) pair.
    """
    fig = go.Figure()

    for sector, group in df.groupby(group_col, sort=False):
        is_highlighted = sector == highlighted_sector
        fig.add_trace(
            go.Scatter(
                x=group[x_col],
                y=group[value_col] * 100,
                mode="lines",
                name=sector,
                line={
                    "width": 3 if is_highlighted else 1.5,
                    "color": colors.EMPHASIS_ACCENT if is_highlighted else colors.DEEMPHASIS_GRAY,
                },
                opacity=1.0 if is_highlighted else 0.55,
                showlegend=is_highlighted,
                hovertemplate=f"<b>{sector}</b><br>%{{y:.1f}}%<extra></extra>",
            )
        )

    fig.update_layout(**_base_layout(height=340))
    fig.update_xaxes(**_axis())
    fig.update_yaxes(**_axis(title="Cumulative return (%)"))
    return fig


def diverging_bar_chart(df: pd.DataFrame) -> go.Figure:
    """Horizontal diverging bar: naive-minus-PIT difference, one bar per sector.

    Sorted by absolute magnitude so the largest divergence - the headline
    finding - sits at the top. Positive (naive overstates) in the diverging
    "positive" hue, negative (naive understates) in the diverging "negative"
    hue, per theme/colors.py.
    """
    plot_df = df.dropna(subset=["difference_pp"]).sort_values("abs_difference_pp", ascending=True)

    bar_colors = [
        colors.DIVERGING_POSITIVE if v >= 0 else colors.DIVERGING_NEGATIVE
        for v in plot_df["difference_pp"]
    ]

    fig = go.Figure(
        go.Bar(
            y=plot_df["gics_sector"],
            x=plot_df["difference_pp"],
            orientation="h",
            marker={"color": bar_colors, "cornerradius": 4},
            text=[f"{v:+.1f} pp" for v in plot_df["difference_pp"]],
            textposition="outside",
            textfont={"size": 11.5, "color": colors.INK_SECONDARY},
            hovertemplate="<b>%{y}</b><br>%{x:+.1f} pp<extra></extra>",
        )
    )

    fig.add_vline(x=0, line_width=1, line_color=colors.BASELINE)

    # Outside data-labels need headroom past the longest bar or they clip
    # against the plot edge - pad the range by 18% of the observed span.
    max_abs = plot_df["difference_pp"].abs().max()
    pad = max_abs * 0.18 if max_abs > 0 else 1
    span_min = min(0, plot_df["difference_pp"].min()) - pad
    span_max = max(0, plot_df["difference_pp"].max()) + pad

    fig.update_layout(
        **_base_layout(
            height=max(320, 34 * len(plot_df)),
            showlegend=False,
            margin={"l": 10, "r": 60, "t": 10, "b": 10},
        )
    )
    fig.update_xaxes(
        **_axis(title="Naive minus point-in-time (percentage points)"),
        range=[span_min, span_max],
    )
    fig.update_yaxes(
        showgrid=False, showline=False, tickfont={"size": 12, "color": colors.INK_PRIMARY}
    )
    return fig


def paired_bar_chart(df: pd.DataFrame, sectors: list[str]) -> go.Figure:
    """Naive vs. point-in-time cumulative return, side by side, for a shortlist.

    The one chart in this dashboard that uses the reserved status pair
    (good/critical) - because it is directly encoding "correct" vs. "wrong,"
    the exact case that pair exists for.
    """
    plot_df = df[df["gics_sector"].isin(sectors)].copy()
    plot_df["gics_sector"] = pd.Categorical(
        plot_df["gics_sector"], categories=sectors, ordered=True
    )
    plot_df = plot_df.sort_values("gics_sector")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Naive (today's sector)",
            x=plot_df["gics_sector"],
            y=plot_df["naive_cumulative_return"],
            marker={"color": colors.NAIVE_COLOR, "cornerradius": 4},
            hovertemplate="<b>%{x}</b><br>Naive: %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Point-in-time correct",
            x=plot_df["gics_sector"],
            y=plot_df["pit_cumulative_return"],
            marker={"color": colors.PIT_COLOR, "cornerradius": 4},
            hovertemplate="<b>%{x}</b><br>Point-in-time: %{y:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(**_base_layout(height=380, barmode="group", bargap=0.28, bargroupgap=0.08))
    fig.update_xaxes(**_axis())
    fig.update_yaxes(**_axis(title="Cumulative return, common period (%)"))
    return fig
