"""Point-in-Time Analytics Lab — Streamlit entry point.

Run locally with::

    streamlit run dashboard/app.py

Deployed on Streamlit Community Cloud pointed at this file, using only
requirements.txt (5 packages — no dbt, no PostgreSQL driver; see that file's
header comment). The app reads Parquet artefacts from data/processed/,
produced by ``python -m pit_lab.export`` — it never connects to a database
itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit's script runner puts this file's directory on sys.path, not the
# repo root, so `from dashboard.x import y` would fail without this. Inserted
# before any first-party import.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st  # noqa: E402

from dashboard.components.sidebar import inject_css, render_brand, render_footer  # noqa: E402
from dashboard.views import (  # noqa: E402
    architecture,
    business_impact,
    data_quality,
    gold_dashboard,
    methodology,
    overview,
    performance,
    sql_depth,
)

st.set_page_config(
    page_title="Point-in-Time Analytics Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
render_brand()

pages = [
    st.Page(overview.render, title="Overview", icon="🏠", url_path="overview", default=True),
    st.Page(architecture.render, title="Architecture", icon="🗂️", url_path="architecture"),
    st.Page(sql_depth.render, title="SQL Depth", icon="🧮", url_path="sql-depth"),
    st.Page(gold_dashboard.render, title="Gold Dashboard", icon="📊", url_path="gold-dashboard"),
    st.Page(performance.render, title="Performance", icon="⚡", url_path="performance"),
    st.Page(data_quality.render, title="Data Quality", icon="✅", url_path="data-quality"),
    st.Page(business_impact.render, title="Business Impact", icon="💼", url_path="business-impact"),
    st.Page(methodology.render, title="Methodology", icon="📚", url_path="methodology"),
]

navigation = st.navigation(pages, position="hidden")

# st.navigation's own sidebar widget always claims a fixed slot at the very
# top of the sidebar, regardless of call order relative to other sidebar
# content - which conflicts with the standard's logo-first layout. Hiding it
# and rendering the nav manually with st.page_link (which still carries the
# automatic active-page highlighting) keeps the intended order: brand, then
# nav, then footer.
for page in pages:
    st.sidebar.page_link(page)

render_footer()
navigation.run()
