"""08 - Methodology: sourcing, exclusions, and limitations — stated, not buried."""

from __future__ import annotations

import streamlit as st

from dashboard.components.data import load_excluded_tickers

SOURCE_TABLE = [
    (
        "S1",
        "Compensia — GICS Code Changes exhibit (Oct 2018)",
        "Company-by-company change table, the 2018 event's primary transcription source",
    ),
    ("S2", "Callan — The New Communication Services Sector", "Institutional consultant analysis"),
    (
        "S3",
        "S&P Dow Jones Indices — Introducing the S&P Global 1200 Communication Services Sector",
        "Index provider (primary), Sep 13 2018",
    ),
    ("S4", "Wikipedia — Communication services sector reshuffle", "Tertiary, corroborating"),
    (
        "S5",
        "LSEG / Lipper Alpha — 2023 GICS Classification Change",
        "Names all 14 affected S&P 500 constituents",
    ),
    (
        "S6",
        "S&P DJI & MSCI — 2023 GICS structure revisions press release",
        "Index provider (primary)",
    ),
    ("S7", "FW Cook — GICS sub-industry changes summary, March 2023", "Advisory-firm summary"),
    (
        "S8",
        "Nareit / S&P DJI — Real Estate 11th GICS sector",
        "Index provider (primary), effective after close 2016-08-31; S&P 500 implementation 2016-09-16",
    ),
    ("S9", "GICS structure documentation", "Sectors present since the 1999 GICS inception"),
]


def render() -> None:
    st.markdown('<div class="pit-eyebrow">08 · Methodology</div>', unsafe_allow_html=True)
    st.header("Sourcing, exclusions, and limitations")
    st.markdown(
        '<p class="pit-lede">The sector-reclassification seed table is the '
        "one hand-curated table in this project. Every row traces to a "
        "documented source — nothing is inferred from price behaviour or "
        "invented. This page is the full account, not a footnote.</p>",
        unsafe_allow_html=True,
    )

    st.subheader("Primary sources")
    st.dataframe(
        {
            "ID": [s[0] for s in SOURCE_TABLE],
            "Source": [s[1] for s in SOURCE_TABLE],
            "Role": [s[2] for s in SOURCE_TABLE],
        },
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Full detail, including the date-off-by-one convention, is in docs/sector_sources.md."
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Why the analysis window starts 2016-10-03")
    st.markdown(
        """
Not arbitrary. Two GICS sectors were created inside the price corpus's
2015–2025 span: **Real Estate** (S&P 500 implementation after close
2016-09-16) and **Communication Services** (2018-09-24). Constituent-level
history is sourced for the Communication Services event but not for the Real
Estate one, so the window opens after the Real Estate separation completed —
leaving exactly one, fully-sourced sector-creation event inside the analysis
window.
        """
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Known limitations, stated explicitly")

    with st.expander("Survivorship bias in the price corpus"):
        st.markdown(
            """
The OHLCV dataset covers *current* S&P 500 constituents only. Four seed-table
tickers have no price history and cannot contribute to the anchor metric:
**TWTR** (delisted, taken private 2022), **ATVI** (acquired by Microsoft
2023), **TRIP** and **ETSY** (removed from the index). They remain in the
seed — the seed is the historical record, not a convenience subset — but the
gap means the measured anchor-metric effect is a **lower bound**: the true
impact of the 2018 restructure was larger than this corpus can show.
            """
        )

    with st.expander("Entity discontinuity — backfilled tickers held out"):
        st.markdown(
            """
Six tickers were excluded not because of a source-mismatch but by deliberate
decision, because their price series is backfilled across a corporate
restructuring (a merger, spin-off, or entity rename) that makes "this ticker
never changed sector" provably wrong with no source available to replace the
assumption: **WBD** (Warner Bros. Discovery, formed 2022), **PSKY** (Paramount
Skydance, successor to a 2019 re-merger, recapitalised again 2025), **TKO**
(TKO Group, formed 2023 from WWE + UFC), **FOXA/FOX** (Fox Corporation began
trading 2019-03-12 — a different legal entity from the Fox reclassified in
2018), and **TTD** (Trade Desk — currently Communication Services, which did
not exist before 2018-09-24, but no source names its earlier sector
individually).
            """
        )
        excluded = load_excluded_tickers()
        held_out = excluded[excluded["present_in"].str.startswith("held_out", na=False)]
        if not held_out.empty:
            st.dataframe(
                held_out[["ticker", "present_in", "exclusion_reason"]],
                width="stretch",
                hide_index=True,
            )

    with st.expander("Sub-industry coverage is partial by design"):
        st.markdown(
            """
`old_gics_sub_industry` / `new_gics_sub_industry` are populated only where a
source document listed them explicitly. For the Media & Entertainment cohort
that moved as an entire industry group, these columns are left **NULL rather
than guessed** — sector is this project's analytical grain; sub-industry is
documentation, and inventing plausible values would violate the sourcing
standard this page exists to uphold.
            """
        )

    with st.expander("Equal-weighted, not cap-weighted, sector returns"):
        st.markdown(
            """
The price corpus carries no shares-outstanding or market-capitalisation
column, so every sector index in this project is an equal-weighted,
daily-rebalanced mean of its constituents' returns — not a cap-weighted index
comparable to a published sector ETF. This does not affect the point-in-time
demonstration (the naive and correct series use identical weighting, so the
comparison is apples-to-apples), but it does mean these are not investable
sector benchmarks.
            """
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Every excluded ticker")
    excluded = load_excluded_tickers()
    st.dataframe(excluded, width="stretch", hide_index=True)

    st.markdown(
        """
        <div class="pit-footer-note">
        Point-in-Time Analytics Lab · <a href="https://github.com/pinheiro-dataworks" target="_blank">Renan Pinheiro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
