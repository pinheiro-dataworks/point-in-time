"""06 - Data Quality: the dbt test suite, run for real, shown for real."""

from __future__ import annotations

import streamlit as st

TESTS = [
    {
        "name": "assert_no_overlapping_validity_ranges",
        "desc": "No ticker has two dimension rows with overlapping date ranges.",
        "why": "An overlap would make the point-in-time range join ambiguous — two rows would both claim a given trade date.",
    },
    {
        "name": "assert_exactly_one_current_row",
        "desc": "Every ticker has exactly one is_current = TRUE row.",
        "why": "Zero means no present-day sector exists to naive-join against; more than one makes the naive join non-deterministic.",
    },
    {
        "name": "assert_no_gaps_in_validity_ranges",
        "desc": "No observed trading day falls in a gap between two dimension versions.",
        "why": (
            "Checked against the real trading calendar, not calendar-day adjacency — both "
            "reclassification events took effect over a weekend, so a naive '+1 day' check "
            "flags all 31 reclassified tickers as false positives. See the SQL Depth page."
        ),
    },
    {
        "name": "assert_fact_dimension_referential_integrity",
        "desc": "Every (ticker, trade_date) resolves to exactly one dimension row.",
        "why": "The direct proof that the range join in gold.fact_returns_pit never drops or duplicates a fact row.",
    },
    {
        "name": "assert_reclassified_ticker_has_multiple_versions",
        "desc": "Every ticker in the sourced seed table has ≥ 2 dimension rows.",
        "why": "Unique to this dataset — directly checkable against sector_history because every event is a documented source, not a derived rule.",
    },
    {
        "name": "assert_dim_reconciliation_is_empty",
        "desc": "The SCD2 replay lands exactly on today's constituent snapshot.",
        "why": "Caught nothing in the final build, but caught real gaps during development — see Methodology.",
    },
    {
        "name": "assert_no_sector_existence_violations",
        "desc": "No dimension row claims a sector before it existed (or after it was retired) under GICS.",
        "why": "This is the exact check that surfaced LYV and TMUS missing from the original seed — a genuine defect this test suite found, not a hypothetical.",
    },
]


def render() -> None:
    st.markdown('<div class="pit-eyebrow">06 · Data Quality</div>', unsafe_allow_html=True)
    st.header("dbt tests — temporal integrity")
    st.markdown(
        '<p class="pit-lede">Because a point-in-time dimension is only as '
        "trustworthy as its guarantees against overlap and gaps. All 7 "
        "singular tests below, plus 28 generic (not-null / unique / "
        "accepted-values) tests, pass on <code>dbt build</code> — 35 total.</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].markdown(
        '<div class="pit-stat"><div class="v good">40 / 40</div>'
        '<div class="l">dbt build: 3 seeds, 1 snapshot, 1 model, 35 tests</div></div>',
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        '<div class="pit-stat"><div class="v good">0</div>'
        '<div class="l">Rows in silver.dim_reconciliation — SCD2 replay matches today\'s snapshot exactly</div></div>',
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        '<div class="pit-stat"><div class="v good">0</div>'
        '<div class="l">Rows in silver.sector_existence_violations</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    for t in TESTS:
        with st.expander(f"✅  {t['name']}"):
            st.markdown(f"**What it checks:** {t['desc']}")
            st.markdown(f"**Why it matters:** {t['why']}")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("A defect this suite actually found")
    st.markdown(
        """
The sector-existence test is not a hypothetical safeguard — it caught a real
bug while this project was being built. An early version of the SCD2 process
assumed any ticker absent from the seed table had never changed sector. For
eight tickers whose *current* sector is Communication Services, that
assumption was provably false: the sector did not exist until 2018-09-24.
Two of those eight (Live Nation, T-Mobile US) were genuine gaps in the seed
and were added with sourcing; the other six were held out entirely because no
consulted source names their pre-2018 sector individually — see
`dbt_pit/seeds/excluded_entities.csv` and the Methodology page.

That is the intended workflow: a test fails, the failure names a specific
ticker, the fix is either "extend the seed with a sourced event" or "exclude
the entity and record why" — never "loosen the test."
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
