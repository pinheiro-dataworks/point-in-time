"""05 - Performance: real EXPLAIN ANALYZE results, including the honest negatives."""

from __future__ import annotations

import streamlit as st

from dashboard.components.data import load_benchmarks


def render() -> None:
    st.markdown('<div class="pit-eyebrow">05 · Performance</div>', unsafe_allow_html=True)
    st.header("Three query shapes, one real win")
    st.markdown(
        '<p class="pit-lede">Every number and every query plan on this page '
        "was captured from a real run against the warehouse via "
        "<code>python -m pit_lab.benchmark</code> — including the two "
        "benchmarks where the index does <em>not</em> help, reported because "
        "an honest performance page shows the negative case too.</p>",
        unsafe_allow_html=True,
    )

    data = load_benchmarks()
    results = data.get("results", [])

    if not results:
        st.warning(
            "No benchmark results found. Run `python -m pit_lab.benchmark` "
            "to generate data/processed/benchmarks.json."
        )
        return

    cols = st.columns(len(results))
    for col, r in zip(cols, results, strict=True):
        with col:
            tone = "good" if r["speedup"] >= 2 else ("critical" if r["speedup"] < 1.1 else "")
            st.markdown(
                f"""
<div class="pit-stat">
    <div class="v {tone}">{r["speedup"]:.1f}x</div>
    <div class="l"><b>{r["title"]}</b><br>
    {r["before_median_ms"]:.2f} ms → {r["after_median_ms"]:.2f} ms<br>
    {r["verdict"]}</div>
</div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    for r in results:
        with st.expander(f"{r['title']} — {r['verdict']}", expanded=False):
            st.markdown(r["rationale"])
            st.code(r["index_ddl"] + ";", language="sql")
            if r.get("interpretation"):
                st.markdown(f"**Interpretation:** {r['interpretation']}")

            plan_col1, plan_col2 = st.columns(2)
            with plan_col1:
                st.caption("Plan before index")
                st.code(r["before_plan"], language="text")
            with plan_col2:
                st.caption("Plan after index")
                st.code(r["after_plan"], language="text")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("On partitioning")
    st.markdown(
        """
The original project plan proposed yearly declarative partitioning on the fact
table. It is not implemented, and the reason is a measurement rather than a
shortage of time: the fact table is ~1.17M rows and roughly 70 MB, which fits
comfortably in shared buffers, and the indexed sector-aggregation benchmark
above already resolves in single-digit milliseconds. Partitioning earns its
keep at a different scale — a wider universe, intraday bars, or a retention
policy where dropping a partition beats deleting rows — and implementing it
here to report a speed-up the data doesn't actually show would be exactly the
kind of thing this project argues against.
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
