# Point-in-Time Analytics Lab

**Naive joins silently corrupt historical analytics. This project proves it with a real, dated GICS sector reclassification — and fixes it with proper SCD Type 2 modeling.**

[Live dashboard](#) · [Dataset](#dataset) · [Architecture](#architecture) · [Result](#the-result) · [Stack](#stack--zero-cost) · [Reproducing this project](#reproducing-this-project)

---

## The problem

Every sector-based financial report, factsheet, ETF prospectus, or backtest joins a stock's returns to its GICS sector. GICS sectors are not static — the classification committee (S&P Dow Jones Indices / MSCI) reclassifies companies periodically. When a report joins historical returns to a company's **current** sector instead of the sector in effect **on the trade date**, it silently rewrites history.

This happened at scale, twice, in the period this project covers:

- **September 2018** — GICS created a new sector, **Communication Services**, absorbing companies out of Information Technology and Consumer Discretionary. Alphabet, Meta, Netflix, Activision Blizzard, Electronic Arts and others moved sectors on this date — the largest structural change to GICS since its 1999 inception.
- **March 2023** — 14 companies across five GICS sectors were reclassified. Visa, Mastercard and PayPal — three of the largest "Technology" companies at the time — moved to Financials.

Anyone calculating "Technology sector performance, 2016–2018" using **today's** GICS labels would silently exclude Alphabet and include Visa/Mastercard for years they didn't belong there — and report a number that never existed on any given day.

This is not a toy dataset. Every row in the sector-reclassification table this project uses is transcribed from a documented GICS/S&P Dow Jones Indices structural-change bulletin or SEC filing — sourced, dated, and independently verifiable. Full source register: [`docs/sector_sources.md`](docs/sector_sources.md).

---

## The result

Recomputing cumulative sector returns for **Information Technology**, 2016-10-03 to 2025-12-19, using each stock's GICS sector *as classified on the trade date* instead of today's classification, changes the reported return by **+78.2 percentage points** — 62 ticker-sector role assignments and **62,398 individual return observations** filed under the wrong sector by a naive join.

| Sector | Naive % | Point-in-time % | Diff (pp) | Reclassified tickers |
|---|---:|---:|---:|---:|
| Information Technology | 812.1 | 733.9 | **+78.2** | 17 |
| Consumer Staples | 97.3 | 87.2 | +10.0 | 3 |
| Financials | 344.9 | 349.5 | −4.6 | 8 |
| Consumer Discretionary | 385.9 | 390.3 | −4.3 | 12 |
| Telecommunication Services | n/a | 19.5 | n/a | 3 |

Communication Services is the sharper story: it did not exist before 2018-09-24. A naive report compounding from 2016-01-01 anyway publishes a **266.0%** cumulative return for a sector that was absent for **21.4%** of the measurement window; the like-for-like figure, computed only over the period the sector actually existed, is **153.5%**.

Every number above is computed by the warehouse, not hand-entered — reproduce it with `make all` (below) or read it live on the [**Gold Dashboard**](#) page, including the `EXPLAIN ANALYZE` plans behind the performance claims.

---

## Architecture

```
Serving   →  Streamlit dashboard (reads Parquet via DuckDB — no DB at runtime)
Gold      →  fact_returns_pit  (range join on trade date)
              sector_daily_returns / sector_cumulative_returns
              anchor_metric     (naive vs. point-in-time, rebased to a common period)
Silver    →  dim_sector_scd     (hand-rolled SCD Type 2, raw SQL)
              dim_sector_scd_dbt (dbt snapshot — production-automation counterpart)
              fact_returns       (daily returns via LAG)
              sector_existence_violations / dim_reconciliation  (integrity checks)
Bronze    →  daily_prices · sp500_current_snapshot · sector_history · gics_sector_registry
```

No Airflow, on purpose — the project stays SQL-first. Orchestration is a scheduled GitHub Actions job running `dbt build && dbt test` ([`.github/workflows/dbt_ci.yml`](.github/workflows/dbt_ci.yml)).

**Two SCD Type 2 implementations exist side by side, deliberately:**

| | `silver.dim_sector_scd` | `silver.dim_sector_scd_dbt` |
|---|---|---|
| Built by | Hand-rolled SQL (`sql/silver/03_build_dim_sector_scd.sql`) | `dbt snapshot` (`dbt_pit/snapshots/snapshots.yml`) |
| Answers | "What was true in the past" | "Keep this current, automatically, going forward" |
| `valid_from` dates | Real historical dates (2018-09-24, 2023-03-20), reconstructed from source documents | The timestamp of the `dbt snapshot` run that detects a change |
| Can backfill 2018/2023? | Yes — this is what it's for | **No** — `dbt snapshot` is forward-tracking by design; see the file's header comment |

Conflating these two would be the single most common mistake in a project like this. The dashboard's **SQL Depth** page states the distinction explicitly, in the same place it shows both implementations' code.

---

## Dataset

Three real, freely available sources, plus one project-original contribution:

| Source | What it provides | License |
|---|---|---|
| [`fja05680/sp500`](https://github.com/fja05680/sp500) | Current S&P 500 constituents + GICS classification, index membership since 1996 | MIT |
| Kaggle — [S&P 500 Stocks: Daily Historical Data](https://www.kaggle.com/datasets/innacampo/s-and-p-500-stocks-daily-historical-data-10-years) | Daily OHLCV, 501 tickers, 2015-12-21 → 2025-12-19 (1,220,725 rows) | Kaggle dataset license (see source page) |
| **This project** — [`dbt_pit/seeds/sector_history.csv`](dbt_pit/seeds/sector_history.csv) | The sector-reclassification seed: 35 rows, every one sourced from a GICS/S&P DJI bulletin or SEC filing | — original research |

**Known limitations, disclosed rather than hidden** (full detail in [`docs/sector_sources.md`](docs/sector_sources.md) and the dashboard's **Methodology** page):

- The OHLCV corpus covers *current* S&P 500 constituents only — mild survivorship bias. Four reclassified tickers (TWTR, ATVI, TRIP, ETSY) have no price history and are excluded from the return calculation, though they remain in the seed as historical fact.
- Six tickers with backfilled price histories across a corporate restructuring (WBD, PSKY, TKO, FOXA, FOX, TTD) are held out of the analysis universe entirely, because their pre-restructuring sector cannot be sourced — a real example of ticker-identity risk, kept visible rather than silently absorbed.
- Sector returns are equal-weighted, not cap-weighted: the corpus carries no shares-outstanding column.

---

## SQL depth — what actually proves seniority

| Technique | Where | What it proves |
|---|---|---|
| Window functions (`LAG`) | `sql/silver/04_build_fact_returns.sql` | Daily returns per ticker, computed correctly against the *trading* calendar, not date arithmetic |
| Hand-rolled SCD Type 2 | `sql/silver/03_build_dim_sector_scd.sql` | The UPDATE/INSERT mechanism itself — no ORM, no macro hiding it |
| Recursive CTE | `sql/analyses/recursive_sector_chain.sql` | Walking a ticker's version chain — and the exact weekend-gap failure mode a naive calendar-adjacency version hits |
| Range join | `sql/gold/02_build_fact_returns_pit.sql` | The technical core: joining every trade to the sector valid *on that date*, alongside the naive comparison |
| dbt snapshot | `dbt_pit/snapshots/snapshots.yml` | Production-automation SCD2 — and a documented account of what it can and cannot do |
| `EXPLAIN ANALYZE` before/after indexing | `src/pit_lab/benchmark.py`, [`docs/performance.md`](docs/performance.md) | Real query plans for three shapes — including two where the index **does not help**, reported instead of omitted |

**Data quality**: 35 dbt tests (7 singular + 28 generic), all passing on `dbt build`. One of them — the sector-existence check — caught a real bug during development: two tickers (LYV, TMUS) were missing from the original seed table entirely. See [`dashboard`'s Data Quality page](#) for the full account.

---

## Performance — including the honest negatives

| Query shape | Before | After | Speed-up | Verdict |
|---|---:|---:|---:|---|
| Point-in-time sector lookup | 0.33 ms | 0.36 ms | 0.9x | Index does not help — do not add it |
| Sector aggregation over a date range | 318.0 ms | 19.9 ms | **16.0x** | Index is decisive |
| Full range join, whole fact table | 509.6 ms | 514.0 ms | 1.0x | Index does not help — do not add it |

Two of three benchmarks show the index doing nothing, and that is reported rather than cut. The full `EXPLAIN (ANALYZE, BUFFERS)` plans and the reasoning for each result are in [`docs/performance.md`](docs/performance.md) — the file is regenerated from a live run, never hand-edited.

Declarative partitioning was evaluated and **not implemented**: the fact table (~1.17M rows, ~70 MB) fits comfortably in shared buffers, and the indexed aggregation above already resolves in single-digit milliseconds. See `docs/performance.md`'s closing section for the reasoning and the threshold at which partitioning would actually earn its keep.

---

## Stack — zero cost

| Component | Tool | Cost |
|---|---|---|
| Database | PostgreSQL 16 (native install or `docker-compose.yml`) | $0 — open source |
| Transformation | dbt Core 1.12 | $0 — open source |
| Orchestration / CI | GitHub Actions | $0 for public repos |
| Dashboard | Streamlit Community Cloud | $0 |
| Serving data | Parquet via DuckDB (no DB dependency at runtime) | $0 |

Total infrastructure cost: **$0/month.**

---

## Reproducing this project

Requires Python 3.11–3.12 and either a native PostgreSQL 16 install or Docker.

```bash
# 1. Environment
python -m venv .venv
.venv/Scripts/activate           # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
cp .env.example .env             # adjust credentials if not using the defaults

# 2. Warehouse (pick one)
docker compose up -d             # OR use a native PostgreSQL 16 install
createdb pit_lab                 # if not using docker compose

# 3. Data — the small reference CSVs under data/raw/reference/ are already
#    committed. Place the Kaggle OHLCV export under data/raw/prices/ (see
#    docs/project_guide.md section 4 for the exact source), then:
make ingest
make build
make export
make benchmark

# 4. dbt
cp config/profiles.example.yml profiles.yml
make dbt-build

# 5. Run it
make dashboard                   # streamlit run dashboard/app.py
make test                        # pytest (31 tests)
```

`make all` runs steps 3–4 in one command once the raw data is in place. See the [`Makefile`](Makefile) for every target.

---

## Repository layout

```
dashboard/       Streamlit app — 8 pages, reads Parquet only, no DB at runtime
dbt_pit/         dbt project — seeds, snapshot, sources, tests
docs/            Sourcing register, performance report, original project guide
sql/             The hand-rolled pipeline — bronze/silver/gold, numbered and idempotent
src/pit_lab/     Python package — ingest, build orchestration, export, benchmarks
tests/           pytest suite — 31 tests, no live database required
.github/         CI workflow (dbt build && dbt test)
assets/brand/    Logo and layout standard
data/processed/  Committed Gold-layer Parquet artefacts (~1.7 MB) — the dashboard's data
data/raw/reference/  Committed reference CSVs (~80 KB) — what CI runs against
data/raw/prices/     Git-ignored (~106 MB) — source it yourself, see step 3 above
```

---

## Author

Built by **Renan Pinheiro** — [github.com/pinheiro-dataworks](https://github.com/pinheiro-dataworks)

This project pairs with **AdEngine** in the same portfolio: AdEngine proves temporal anti-leakage validation at the model layer; this project builds the point-in-time data layer that validation depends on.
