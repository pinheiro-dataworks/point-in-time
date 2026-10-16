# Design

This document records the problem this project addresses, the decisions behind
its architecture and data model, and the trade-offs that shaped the scope.
Results, numbers, and reproduction steps live in the root [`README.md`](../README.md);
this file is about *why* the system is shaped the way it is.

---

## 1. Problem

Sector-based financial reporting — factsheets, ETF prospectuses, backtests —
joins a stock's historical returns to its GICS sector. GICS sectors are not
static: the classification committee (S&P Dow Jones Indices / MSCI)
periodically reclassifies companies, most notably when it created the
Communication Services sector in September 2018 and revised five sectors in
March 2023. A report that joins historical returns to a company's *current*
sector instead of the sector in effect *on the trade date* silently rewrites
history — exactly the failure mode a point-in-time (SCD Type 2) dimension
exists to prevent.

The same mechanism extends beyond reporting: a sector-classification or
sector-momentum model trained on price history joined to today's sector
labels has target leakage, because the label did not exist in that form on
the date each training row was generated.

Most SCD Type 2 demonstrations use invented data and a self-defined business
rule for the dimension's history. This project deliberately uses a real,
dated, externally verifiable reclassification instead: every row in the
sector-history table is a transcription of a documented GICS/S&P DJI
structural-change bulletin or SEC filing, not an assumption. See
[`sector_sources.md`](sector_sources.md) for the full source register.

---

## 2. Dataset decisions

Three inputs, chosen so that no part of the dimension history is invented:

- **Index membership and current GICS classification** (`fja05680/sp500`) —
  downloaded verbatim; index providers publish current state but not a dated
  history of sector changes.
- **Daily OHLCV prices** (Kaggle, 10-year S&P 500 export) — a static,
  freely available corpus. It covers only *current* S&P 500 constituents,
  which introduces mild survivorship bias; this is disclosed rather than
  hidden, and four reclassified tickers with no price history (TWTR, ATVI,
  TRIP, ETSY) are excluded from the return calculation while remaining in the
  seed table as historical fact.
- **Sector-reclassification history** — the one input with no ready-made
  download, because reconstructing *when* each company's sector changed is
  the actual analytical work a point-in-time dimension requires. It is
  hand-curated from primary documents (GICS bulletins, SEC filings) and
  committed as `dbt_pit/seeds/sector_history.csv`.

Returns are equal-weighted rather than cap-weighted, because the corpus
carries no shares-outstanding column — a disclosed limitation, not an
estimate.

---

## 3. Architecture decisions

The pipeline follows a Bronze → Silver → Gold layering, with no workflow
orchestrator: the project stays SQL-first, and a scheduled GitHub Actions job
running `dbt build && dbt test` is the only scheduling layer. At this data
volume and update cadence (a weekly check for new GICS reviews, not a
continuously arriving stream), an orchestrator would add operational surface
without buying anything the scheduled CI job doesn't already provide.

**Two SCD Type 2 implementations exist side by side, deliberately:**

| | `silver.dim_sector_scd` | `silver.dim_sector_scd_dbt` |
|---|---|---|
| Built by | Hand-rolled SQL | `dbt snapshot` |
| Demonstrates | The UPDATE/INSERT mechanism itself | Production-grade automation |
| `valid_from` dates | Real historical dates (2018-09-24, 2023-03-20) | The timestamp of the snapshot run that detects a change |
| Can backfill 2018/2023? | Yes | No — `dbt snapshot` is forward-tracking by design |

The dbt snapshot cannot reconstruct a change that happened before the first
snapshot run, which is why the hand-rolled table — not the dbt one — carries
the dimension's real historical dates. Conflating the two would be the most
common mistake a project like this could make, so both are kept, and the
distinction is stated explicitly in the dashboard.

Partitioning (yearly, on the fact table) was evaluated and not implemented:
at ~1.17M rows / ~70 MB, the table fits comfortably in shared buffers, and an
indexed aggregation already resolves in single-digit milliseconds. See
[`performance.md`](performance.md) for the benchmark and the threshold at
which partitioning would earn its keep.

---

## 4. Data model

- **Grain.** `fact_returns` / `fact_returns_pit` are one row per
  ticker/trade-date. `dim_sector_scd` is one row per ticker/sector-version,
  with `valid_from`, `valid_to`, and `is_current`.
- **`change_type`.** The seed table distinguishes `reclassification` (a
  company moved sector) from `sector_rename` (the sector's name changed, the
  company didn't move — e.g. Telecommunication Services renaming to
  Communication Services for AT&T and Verizon). Collapsing the two would
  overstate the size of the reclassification effect, so the anchor metric
  counts only true reclassifications.
- **Date convention.** Both headline reclassifications took effect *after
  the close* of a Friday. The seed table carries both
  `effective_after_close` (last trading day under the old classification)
  and `first_trading_day` (first day under the new one); the SCD2 build uses
  `valid_to = effective_after_close` and `valid_from = first_trading_day`.
  Using the announcement date, or using `effective_after_close` as the new
  row's `valid_from`, would misclassify one trading day per affected ticker —
  a small error, but exactly the class this project exists to demonstrate.
- **Entity identity.** `FOXA`'s price history begins 2019-03-12, after the
  modern Fox Corporation started trading post-spinoff — a different legal
  entity from the `FOXA` that existed in the 2018 reclassification. Treating
  them as the same ticker would attribute the new company's history to the
  old company's reclassification, so `FOXA` is excluded from the seed table
  rather than silently merged. The general lesson — ticker reuse argues for
  keying a point-in-time dimension on a stable entity identifier rather than
  the ticker string — is recorded here because this corpus offers no other
  join key.

Full sourcing detail and confidence tiers for every seed row are in
[`sector_sources.md`](sector_sources.md).

---

## 5. Scope boundaries

Primary-source research was time-boxed to the two unambiguous headline
events (September 2018, March 2023), where dates and affected tickers are
unambiguous in SEC filings and index-provider bulletins. Extending the seed
table to every GICS review year is possible without changing the SCD2 logic
or any downstream model, but was left out to keep every row independently
verifiable rather than trading that standard for broader coverage.
