# Point-in-Time Analytics Lab — Project Guide
### Full Scope, Zero Cost to Production | SQL Depth + Senior Data Scientist Positioning
### Dataset: S&P 500 constituents + GICS sector reclassification

**Prepared for:** Renan Pinheiro
**Date:** August 2026
**Language:** English (repository, code, commits, documentation, dashboard — no Portuguese artifacts)
**Status:** Implemented. This is the original planning document; **README.md at the repository root is the current source of truth** for architecture, results and stack. Figures in this document marked "illustrative" have since been superseded by the real, computed results in `gold.anchor_metric` — see the README's "The result" section and the dashboard's Gold Dashboard / Business Impact pages. The HTML prototype referenced below (`docs/prototype/pit-lab-prototype.html`) was the pre-build design mock; the shipped interface is the Streamlit app under `dashboard/`.

---

## 1. Overview

**One-line pitch:** "How much of a sector's historical return is actually just companies that got reclassified after the fact — and what happens when a report joins returns to the sector label a stock has *today*, instead of the one it had on the day of the trade?"

**Project name:** Point-in-Time Analytics Lab
**README tagline:** "Naive joins silently corrupt historical analytics. This project proves it with a real, dated GICS sector reclassification — and fixes it with proper SCD Type 2 modeling."

This keeps the exact same technical spine as the original Olist-based plan — SCD Type 2, range joins, dbt snapshots, recursive CTEs — but swaps the domain for one where the underlying dimension change is a **real, third-party, dated event**, not a rule you defined yourself. That removes the one disclosure the Olist version needed ("this tier is a business assumption I applied to real data") and replaces it with something stronger: "this sector history is transcribed from GICS/S&P index-provider reclassification bulletins and SEC filings."

---

## 2. The Business Problem (real, recurring, international)

### 2.1 What happens in practice

Every sector-based financial report, factsheet, ETF prospectus, or backtest joins a stock's returns to its GICS sector. GICS sectors are not static — the classification committee (S&P Dow Jones Indices / MSCI) reclassifies companies periodically. When a report or backtest joins historical returns to a company's **current** sector instead of the sector in effect **on the trade date**, it silently rewrites history: a 2016 return for Alphabet gets attributed to "Communication Services," a sector that would not exist for another two years.

This is not a hypothetical. It happened at scale, twice, in the period this project covers:

- **September 2018** — GICS created a new sector, Communication Services, absorbing the Media & Entertainment industry group from Consumer Discretionary and the Telecommunication Services, Internet Software & Services, and Home Entertainment Software sub-industries from Information Technology. Alphabet (GOOGL/GOOG), Meta (then Facebook, FB), Netflix (NFLX), and Twitter (TWTR) all moved sectors on this date. S&P Dow Jones Indices and MSCI called it the largest GICS structural change (by market-cap impact) since the standard's 1999 inception.
- **March 2023** — 14 companies across five GICS sectors were reclassified. Visa (V), Mastercard (MA), and PayPal (PYPL) — three of the largest "Technology" companies at the time — moved to Financials.

Anyone who calculated "Technology sector performance, 2015–2018" using today's GICS labels would be quietly excluding Google and including Visa/Mastercard in the wrong sector for years they didn't belong there — and would report a number that never actually existed on any given day.

### 2.2 Why this matters in 2026 — not a textbook problem

- **It is a recurring interview topic.** SCD questions appear in roughly a third of data-modeling interview segments and are close to mandatory at companies that mention data warehousing or analytics engineering in the job description — this doesn't change with the dataset.
- **This is literal financial-industry vocabulary, not an analogy.** "Point-in-time" (PIT) databases exist specifically in institutional finance to prevent **look-ahead bias** and **survivorship bias** in backtests. Framing this project around a real GICS reclassification means "point-in-time correctness" stops being a metaphor borrowed from e-commerce and becomes the actual term practitioners use.
- **It connects directly to ML integrity, not just reporting.** A "sector classification" or "sector momentum" model trained on historical price data joined to today's sector labels has textbook target leakage — the same category of problem addressed by the temporal anti-leakage validation in AdEngine. This project builds the data layer that makes that kind of validation possible in the first place.

### 2.3 The angle you can own

Most SCD tutorials use invented or toy data. This project uses a real, dated, externally-verifiable reclassification event as the dimension history — no synthetic data, no self-defined business rule, and a data source (SEC filings, GICS bulletins) any interviewer can independently check.

---

## 3. Why This Is a Senior Data Scientist Project, Not Just a Data Engineering One

Point-in-time correctness isn't only about clean reporting — it's a prerequisite for statistical integrity. If a model's features, or a backtest's returns, are computed using a dimension's *current* state instead of its state at the event date, that's target leakage disguised as a join bug. It's the same principle behind the temporal anti-leakage validation built into AdEngine — this project builds the data layer that makes that kind of validation possible in the first place.

This creates the same strong cross-project narrative as before: AdEngine proves you know how to validate; Point-in-Time Analytics Lab proves you know how to build the data foundation that validation depends on. With the S&P 500/GICS pivot, the finance framing is no longer an analogy — "point-in-time" and "look-ahead bias" are literal terms used in quant research and index construction, which makes the throughline to AdEngine tighter, not looser.

---

## 4. Dataset — Technical Honesty Approach

Three real, freely available sources. No invented business rule anywhere in this version.

**a) Historical S&P 500 index membership (which tickers were in the index, by date, since 1996)**
Repository: `fja05680/sp500` (MIT license, actively maintained)
File: `S&P 500 Historical Components & Changes (Updated).csv`
Direct link: https://github.com/fja05680/sp500/blob/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv

**b) Current constituent snapshot, including GICS Sector and GICS Sub-Industry per ticker**
Same repository, file: `sp500.csv`
Raw CSV: https://raw.githubusercontent.com/fja05680/sp500/master/sp500.csv
Columns include Symbol, Security, GICS Sector, GICS Sub-Industry, Headquarters, Date added, CIK, Founded. This is the "arrival state" you work backward from when building the SCD2 dimension.

**c) Sector-reclassification seed table (the actual SCD2 change events) — you build this, sourced from primary documents**
This is the one piece with no single ready-made download, and that's the point: it's real historical fact-finding, not invention. Confirmed anchor events to start from:

| Ticker | Old GICS Sector | New GICS Sector | Effective date | Primary source |
|---|---|---|---|---|
| GOOGL / GOOG (Alphabet) | Information Technology | Communication Services | Sep 2018 | GICS structural change bulletins, SEC 424B2/497 filings referencing the Sep 21, 2018 rebalance |
| META (then FB) | Consumer Discretionary | Communication Services | Sep 2018 | same |
| NFLX (Netflix) | Consumer Discretionary | Communication Services | Sep 2018 | same |
| TWTR (Twitter) | Information Technology | Communication Services | Sep 2018 | same |
| V (Visa) | Information Technology | Financials | Mar 17, 2023 | GICS 2023 annual review bulletin |
| MA (Mastercard) | Information Technology | Financials | Mar 17, 2023 | same |
| PYPL (PayPal) | Information Technology | Financials | Mar 17, 2023 | same |

Expanding this table to the full list (14 tickers across 5 sectors in 2023; the complete 2018 list) is Phase 1 work — see the Roadmap. State the sourcing explicitly in the README:

> "`sector_history.csv` is reconstructed from documented GICS/S&P Dow Jones Indices structural-change bulletins and SEC filings referencing the September 2018 and March 2023 reclassifications. It is not inferred, estimated, or invented. Full source list in `/docs/sector_sources.md`."

This is a *lighter* disclosure than Olist's tier rule needed, because nothing here is a judgment call you made — every row is a transcription of a real classification-committee decision with a public paper trail.

**d) Daily OHLCV price data (the fact table)**
Static Kaggle CSV, current S&P 500 constituents, per-ticker files, 2015–2025:
https://www.kaggle.com/datasets/innacampo/s-and-p-500-stocks-daily-historical-data-10-years
Alternative with longer history (since 1962) if you want more room before the 2018 event:
https://www.kaggle.com/datasets/joebeachcapital/s-and-p500-index-stocks-daily-updated

Avoid depending on `yfinance` for anything beyond a spot-check — Yahoo Finance's February 2025 site redesign broke a lot of scripts built on it (schema and quota changes). If you need fresher data than the Kaggle cutoff, **Stooq** (no API key required) is the more commonly recommended free fallback right now.

**Known scope limitation to disclose (same technical-honesty pattern as Olist):** the Kaggle OHLCV sources cover *current* S&P 500 constituents only, so there's mild survivorship bias in the price data itself. This doesn't undermine the SCD2/point-in-time demonstration — every ticker in the reclassification seed table is still a current constituent — but it means this isn't a rigorous investment backtest, and the README should say so.

---

## 5. Architecture

```
Serving        →  Streamlit Dashboard
Gold           →  fact_returns_pit (range join on trade date)
                   Naive vs. point-in-time correct sector return comparison
Silver         →  sector_history seed table (curated, SQL)
                   Hand-rolled SCD Type 2 (raw SQL)
                   dbt snapshot (production automation)
                   dim_sector_scd (valid_from / valid_to / is_current)
Bronze         →  Raw tables: sp500 membership, sp500 current snapshot, daily OHLCV
```

Same reasoning as before on orchestration: no Airflow. GitHub Actions running `dbt build && dbt test` on a schedule stays the differentiator within your own portfolio.

---

## 6. Technical SQL Scope — What Actually Proves Seniority

| Layer | Technique | What it proves | Applied to this dataset |
|---|---|---|---|
| Silver | Window functions (LAG, LEAD, ROW_NUMBER) | Fluency with analytic functions | Compute daily/monthly returns per ticker from close price; flag the row where a ticker's sector label changes |
| Silver | Hand-rolled SCD Type 2 (no dbt) | Understanding the underlying mechanism | INSERT/UPDATE logic on `dim_sector_scd`, seeded from `sector_history.csv` |
| Silver | dbt snapshot (`check_cols` strategy) | Production-grade automation | Reproduces the hand-rolled result via dbt |
| Silver | Recursive CTE | One of the most cited senior-SQL differentiators | Walk a ticker's full sector version chain, e.g. GOOGL: *Internet Software & Services (Info Tech)* → *Interactive Media & Services (Communication Services)* |
| Gold | Range join (`BETWEEN valid_from AND COALESCE(valid_to, '9999-12-31')`) | The technical core of the project | Join `fact_returns_pit` to the sector valid on the trade date |
| Gold | Naive vs. correct sector return | The quantified business metric | Same price series, two different sector joins — see Section 7 |
| Performance | `EXPLAIN ANALYZE` before/after composite index (`ticker, valid_from, valid_to`) + yearly partitioning | Query-cost awareness | Same pattern as before |
| Quality | Custom dbt tests: no overlapping ranges, exactly one `is_current = true` per ticker, fact-to-dimension referential integrity, **every reclassified ticker has ≥2 dimension rows** | Engineering rigor | The last test is new and unique to this dataset — directly checkable against the seed table, unlike a derived business rule |

---

## 7. Anchor Metric (the headline result)

> "Recalculating cumulative sector returns for Information Technology and Communication Services, [YYYY]–[YYYY], using each stock's GICS sector *as classified on the trade date* instead of today's classification, changed the reported return of [sector] by **X percentage points** and reassigned **Y** reclassified companies' historical performance out of a sector that, for [Z]% of the period measured, did not yet exist."

X, Y, and Z stay placeholders — marked illustrative — until Phase 4 execution against the real warehouse, exactly the same technical-honesty rule as the Olist version.

**Framing angles:**
- **Financial/audit framing:** misstatement risk in sector-return figures that feed factsheets, ETF marketing material, or performance-attribution reports.
- **Regulatory framing:** ties directly to Section 2.2 — SEC/FINRA disclosure integrity for sector-based investment products is a real, current compliance concern, not an invented analogy.
- **ML framing:** identical mechanism to AdEngine's temporal anti-leakage validation — training a sector-classification or sector-momentum model on backfilled labels is target leakage, with a real historical example attached.

---

## 8. Stack — Zero Cost to Production (unchanged, verified August 2026)

| Component | Tool | Free tier | Notes |
|---|---|---|---|
| Database | Neon (Postgres serverless) | 0.5 GB storage, 100 compute-hours/month, no credit card | Branching still doubles as a nice narrative hook for testing SCD logic changes in isolation |
| Local alternative | Docker Compose + Postgres | Free | Offline development |
| Transformation | dbt Core | Open source | Snapshots, tests, docs |
| Orchestration | GitHub Actions (scheduled) | Free for public repos | `dbt build && dbt test` |
| Dashboard | Streamlit Community Cloud | Free | Same pattern as your other projects |
| Version control | GitHub | Free | Public, README in English |
| CI | GitHub Actions | Free | Runs on every push |

Total cost: $0. Same constraint to watch: Neon's 100 compute-hours/month.

---

## 9. Deliverables

All produced directly in English.

1. Public GitHub repository, README following your standard structure (problem → architecture → result → stack).
2. `sql/` directory with the hand-rolled SCD Type 2 implementation, commented in English.
3. dbt project (`models/`, `snapshots/`, `tests/`), `schema.yml` descriptions in English.
4. Performance benchmark section (`EXPLAIN ANALYZE` before/after), in English.
5. Streamlit dashboard with a "Naive vs. Point-in-Time Correct" toggle showing the anchor metric.
6. `docs/sector_sources.md` — the primary-source list backing every row of `sector_history.csv` (GICS bulletins, SEC filing references, dates).
7. README "Methodology Note" disclosing the sourcing approach for the sector-reclassification table.
8. Commit messages in English, Conventional Commits style (`feat:`, `fix:`, `test:`).

---

## 10. Roadmap by Phase (part-time pace)

| Phase | Scope | Estimate |
|---|---|---|
| 0 — Setup | Neon/Docker, dbt scaffold, ingest sp500 membership + snapshot + Kaggle OHLCV | 2–3h |
| 1 — Sector reclassification seed table | Research and transcribe the Sep 2018 and Mar 2023 GICS events from primary sources into `sector_history.csv` (ticker, old_sector, new_sector, effective_date, source_url) | 4–6h |
| 2 — Manual SCD | Hand-rolled SCD Type 2 implementation + recursive CTE | 6–8h |
| 3 — dbt snapshot | Production automation + temporal-integrity tests | 4–6h |
| 4 — Gold layer | Range join, naive vs. correct sector return, anchor metric | 6–8h |
| 5 — Performance | Indexing, partitioning, documented `EXPLAIN ANALYZE` | 4–6h |
| 6 — Dashboard | Streamlit build + deploy | 4–6h |
| 7 — README/content | Final documentation, architecture diagram, content prep | 3–4h |
| **Total** | | **~33–47h (4–6 weeks part-time)** |

Phase 1 replaces Olist's "derive the tier rule" step — the hours are comparable, but the deliverable is a sourced transcription instead of a defined business rule.

---

## 11. Risks and Mitigation

| Risk | Mitigation |
|---|---|
| Primary-source research for smaller reclassified tickers is slow or the exact date is ambiguous | Anchor the metric on the two headline events (Sep 2018, Mar 2023), where dates and tickers are unambiguous in SEC filings and index-provider bulletins. Treat full 2018-list coverage and other GICS review years as a stretch goal, not a blocker. |
| Kaggle OHLCV datasets cover current constituents only — mild survivorship bias in price history | Disclose explicitly in the README, same technical-honesty pattern as Olist's licensing disclosure. Doesn't affect the SCD2 demonstration since every seed-table ticker is a current constituent. |
| Scope creep on primary-source research turning into a rabbit hole | Time-box Phase 1 exactly like Phase 1 was time-boxed for Olist — 2 confirmed events are enough for a compelling, defensible anchor metric. |

---

## 12. Portfolio Fit

- Same positioning as before: complements AdEngine — same temporal-integrity concern, data layer instead of model layer.
- **Trade-off from the pivot:** this swaps Olist's Brazil/e-commerce flavor for U.S. index data, more immediately legible to international recruiters, at the cost of the direct throughline to any Brazil-flavored pieces elsewhere in the portfolio. Worth weighing against how much that throughline currently matters to you.
- Content angle: same "MLOps and Data Engineering" niche in your LinkedIn roadmap — the finance framing (look-ahead bias, survivorship bias) may broaden the audience beyond data-engineering readers into quant/fintech readers.

---

## 13. Next Steps

- 🔴 Curate and verify the sector-reclassification seed table for at least the two headline events (Phase 1) before writing any SCD2 code.
- 🔴 Confirm the OHLCV source: Kaggle static CSV (simpler, matches the Olist-style pattern) vs. a live Stooq pull.
- 🟡 Draft the new English README and updated architecture diagram against Sections 5–6 above.
- 🟢 Once the pipeline runs, decide the LinkedIn content angle — the "look-ahead bias" framing may be worth its own post, separate from the SCD2 technical deep-dive.

---

## Sources

- GitHub — `fja05680/sp500`: https://github.com/fja05680/sp500
- Wikipedia — Communication services sector reshuffle: https://en.wikipedia.org/wiki/Communication_services_sector_reshuffle
- Marquette Associates — GICS Reclassifies Away From Tech, Again (2023 reclassification detail)
- Kaggle — S&P 500 Stocks: Daily Historical Data (10 Years): https://www.kaggle.com/datasets/innacampo/s-and-p-500-stocks-daily-historical-data-10-years
- Kaggle — S&P500 index stocks (daily updated): https://www.kaggle.com/datasets/joebeachcapital/s-and-p500-index-stocks-daily-updated
- Archiveteam wiki — Stack Exchange data dump access/licensing status (context for why this dataset was chosen over Stack Exchange): https://wiki.archiveteam.org/index.php/Stack_Exchange
