"""Sidebar brand block and footer — the parts of the standard layout that
sit outside Streamlit's own page-navigation widget.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = REPO_ROOT / "assets" / "brand" / "logo_renan_ds.png"

GITHUB_URL = "https://github.com/pinheiro-dataworks"
APP_VERSION = "v1.0.0"


def render_brand() -> None:
    """Logo, project name and edition badge at the top of the sidebar."""
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), width="stretch")

    st.sidebar.markdown(
        """
        <div class="pit-brand">
            <div class="mark">Portfolio / Analytics Engineering</div>
            <div class="name">Point-in-Time<br>Analytics Lab</div>
            <div class="edition"><span class="dot"></span>S&amp;P 500 / GICS edition</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Author credit and version, pinned near the bottom of the sidebar."""
    st.sidebar.markdown(
        f"""
        <div class="pit-sidebar-footer">
            Built by <strong>Renan Pinheiro</strong><br>
            <a href="{GITHUB_URL}" target="_blank">github.com/pinheiro-dataworks</a><br>
            <span style="opacity:0.6;">{APP_VERSION}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_css() -> None:
    css_path = Path(__file__).resolve().parents[1] / "theme" / "style.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True
        )
