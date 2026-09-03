"""03 - SQL Depth: the actual SQL, read live from sql/, never a transcription."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str, start: str | None = None, end: str | None = None) -> str:
    """Read a SQL file, optionally slicing between two marker substrings.

    Reading straight from sql/ rather than pasting a copy means this page can
    never silently drift out of sync with the SQL that actually runs.
    """
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    if start:
        text = text[text.index(start) :]
    if end:
        text = text[: text.index(end)]
    return text.strip()


def render() -> None:
    st.markdown('<div class="pit-eyebrow">03 · SQL Depth</div>', unsafe_allow_html=True)
    st.header("Four techniques, one mechanism")
    st.markdown(
        '<p class="pit-lede">Window functions to detect the change, '
        "hand-rolled SCD2 to understand it, dbt to automate it, a recursive "
        "CTE to audit it, and a range join to actually use it correctly. "
        "Every snippet below is read live from the SQL files that run — "
        "not a transcription.</p>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(
        [
            "Window functions",
            "Hand-rolled SCD2",
            "Recursive CTE",
            "Range join",
            "dbt snapshot",
        ]
    )

    with tabs[0]:
        st.caption("sql/silver/04_build_fact_returns.sql — daily returns via LAG")
        st.code(
            _read(
                "sql/silver/04_build_fact_returns.sql",
                start="WITH priced AS",
                end="ANALYZE",
            ),
            language="sql",
        )

    with tabs[1]:
        st.caption("sql/silver/03_build_dim_sector_scd.sql — the UPDATE/INSERT cycle")
        st.code(
            _read(
                "sql/silver/03_build_dim_sector_scd.sql",
                start="DO $scd$",
                end="$scd$;",
            )
            + "\n$scd$;",
            language="sql",
        )
        st.info(
            "Runs once per distinct event date, not once per row — two "
            "iterations total for this dataset, and correct for any number "
            "of future GICS reviews appended to the seed.",
            icon="ℹ️",
        )

    with tabs[2]:
        st.caption("sql/analyses/recursive_sector_chain.sql — gap-tolerant chain walk")
        st.code(
            _read(
                "sql/analyses/recursive_sector_chain.sql",
                start="WITH RECURSIVE sector_chain AS (\n\n    SELECT\n        d.ticker,\n        d.gics_sector,\n        d.valid_from,\n        d.valid_to,\n        d.change_reason,",
                end="ORDER BY depth;\n\n\n-- ===",
            ),
            language="sql",
        )
        st.warning(
            "A naive calendar-adjacency version of this walk (valid_to + 1 "
            "day = next valid_from) fails on both reclassification events, "
            "because they took effect over a weekend. See the full file for "
            "why, and dbt_pit/tests/assert_no_gaps_in_validity_ranges.sql for "
            "the same lesson learned the hard way in the test suite.",
            icon="⚠️",
        )

    with tabs[3]:
        st.caption("sql/gold/02_build_fact_returns_pit.sql — the technical core")
        st.code(
            _read(
                "sql/gold/02_build_fact_returns_pit.sql",
                start="INSERT INTO gold.fact_returns_pit",
                end="WHERE f.daily_return IS NOT NULL;",
            )
            + "\nWHERE f.daily_return IS NOT NULL;",
            language="sql",
        )

    with tabs[4]:
        st.caption("dbt_pit/snapshots/snapshots.yml — production-automation SCD2")
        st.code(_read("dbt_pit/snapshots/snapshots.yml"), language="yaml")
        st.warning(
            "This does NOT reproduce the historical 2018/2023 dates — dbt "
            "snapshot is forward-tracking by design: dbt_valid_from is always "
            "the timestamp of the run that detected a change, not a date "
            "encoded in the data. It correctly captures the NEXT "
            "reclassification once deployed on a schedule. The historically "
            "correct dimension is the hand-rolled one on the previous tabs. "
            "Full reasoning is in the YAML file's own header comment.",
            icon="⚠️",
        )

    st.markdown(
        """
        <div class="pit-footer-note">
        Point-in-Time Analytics Lab · <a href="https://github.com/pinheiro-dataworks" target="_blank">Renan Pinheiro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
