# Sector Reclassification — Primary Sources

`dbt_pit/seeds/sector_history.csv` is the only hand-curated table in this project.
Every row is a **transcription of a documented GICS classification-committee
decision**. Nothing in it is inferred from price behaviour, estimated, or
invented. This document exists so that any reviewer can independently verify
each row against a public document.

---

## 1. Why this file is curated by hand

The two other inputs — index membership and daily OHLCV — are downloaded
verbatim from public sources. The sector *history* is different: index
providers publish the **current** classification of each company, but they do
not publish a free, machine-readable table of *when* each company's sector
changed. That history is what an SCD Type 2 dimension needs, and reconstructing
it from primary documents is the actual analytical work of Phase 1.

This is a deliberately lighter disclosure than a project built on a
self-defined business rule would require: no row here is a judgement call. Each
one is a committee decision with a public paper trail.

---

## 2. Source register

| ID | Source | Type | URL |
|----|--------|------|-----|
| **S1** | Compensia — *GICS Code Changes* exhibit (October 2018). A company-by-company table giving existing GICS sector, existing sub-industry, new sector and new sub-industry. | Advisory-firm transcription of the S&P DJI / MSCI change file | https://compensia.com/wp-content/uploads/2018/10/GICS-Code-Changes-Exhibit-1018.pdf |
| **S2** | Callan — *The New Communication Services Sector* | Institutional consultant analysis | https://www.callan.com/blog-archive/communication-sector/ |
| **S3** | S&P Dow Jones Indices — *Introducing the S&P Global 1200 Communication Services Sector* (Indexology, 13 Sep 2018) | Index provider (primary) | https://www.indexologyblog.com/2018/09/13/introducing-the-sp-global-1200-communication-services-sector/ |
| **S4** | Wikipedia — *Communication services sector reshuffle*, cross-checked against contemporaneous financial press | Tertiary, corroborating | https://en.wikipedia.org/wiki/Communication_services_sector_reshuffle |
| **S5** | LSEG / Lipper Alpha — *2023 GICS Classification Change: Impact on S&P 500 Earnings*, naming all 14 affected S&P 500 constituents; corroborated by S&P DJI's own impact analysis and Marquette Associates | Data vendor + index provider | https://lipperalpha.refinitiv.com/2023/03/2023-gics-classification-change/ |
| **S6** | S&P Dow Jones Indices & MSCI — press release announcing the 2023 GICS structure revisions | Index provider (primary) | https://www.prnewswire.com/news-releases/sp-dow-jones-indices-and-msci-announce-revisions-to-the-global-industry-classification-standard-gics-structure-in-2023-301515447.html |
| **S7** | FW Cook — summary of discontinued and newly created GICS sub-industries, March 2023 | Advisory-firm summary | https://fwcook.com/revisions-to-global-industry-classification-standard-gics-codes-to-be-implemented-in-march-2023/ |

---

## 3. Event 1 — 21 September 2018: creation of Communication Services

S&P Dow Jones Indices and MSCI restructured GICS to create a new sector,
**Communication Services** (code 50). It was the largest structural change to
the standard since its 1999 inception. Mechanically it was three things at once:

1. The existing **Telecommunication Services** sector was *renamed* Communication
   Services. Its incumbents (AT&T, Verizon) did not move — their sector label
   changed underneath them.
2. The **Media & Entertainment** industry group moved in wholesale from
   **Consumer Discretionary**.
3. Selected **Internet Software & Services** and all **Home Entertainment
   Software** companies moved in from **Information Technology**.

A fourth, less-reported consequence: some Internet Software & Services companies
moved from Information Technology to **Consumer Discretionary** rather than to
Communication Services (eBay, Etsy). This project includes those rows because
they make the dimension genuinely multi-directional rather than a single
funnel into one new sector.

### Scale, per S&P Dow Jones Indices and Callan (S2, S3)

Within the S&P 500, **17 stocks moved from Consumer Discretionary** and
**7 stocks moved from Information Technology** into Communication Services —
24 in total, alongside the 3 renamed Telecommunication Services incumbents.

### The `change_type` distinction

The seed table separates `reclassification` from `sector_rename`:

- **`reclassification`** — the company was moved to a different sector.
- **`sector_rename`** — the company stayed put; the sector's *name* changed.

AT&T and Verizon are `sector_rename`. This matters analytically: a naive join
misattributes a reclassified company's history, but for a renamed sector the
label is different without the underlying membership being wrong. Collapsing
the two would overstate the size of the problem, so they are modelled
separately and the anchor metric counts only true reclassifications.

---

## 4. Event 2 — 17 March 2023: GICS annual review

Announced March 2022, effective **after the close of business on Friday,
17 March 2023**. Fourteen S&P 500 constituents changed sector across five
sectors (S5, S6). The mechanism was the discontinuation of the
**Data Processing & Outsourced Services** sub-industry (Information Technology)
and of **General Merchandise Stores** (Consumer Discretionary), with their
constituents redistributed (S7):

| Destination | Count | Tickers |
|---|---|---|
| Information Technology → **Financials** (new *Transaction & Payment Processing Services* sub-industry) | 8 | V, MA, PYPL, FIS, FISV, GPN, JKHY, CPAY |
| Information Technology → **Industrials** (*Human Resource & Employment Services*) | 3 | ADP, PAYX, BR |
| Consumer Discretionary → **Consumer Staples** (*Consumer Staples Merchandise Retail*) | 3 | TGT, DG, DLTR |

All 14 are accounted for, and all 14 are present in the price corpus.

---

## 5. The date convention — and why it is an off-by-one trap

Both events took effect **after the close** of a Friday. The seed table
therefore carries two dates:

| Column | Event 1 | Event 2 | Meaning |
|---|---|---|---|
| `effective_after_close` | 2018-09-21 | 2023-03-17 | Last trading day under the **old** classification |
| `first_trading_day` | 2018-09-24 | 2023-03-20 | First trading day under the **new** classification |

The SCD Type 2 dimension uses:

```
old row:  valid_to   = effective_after_close   (2018-09-21)
new row:  valid_from = first_trading_day       (2018-09-24)
```

Using the announcement date, or using `effective_after_close` as the new row's
`valid_from`, would misclassify one full trading day for every affected ticker.
That is small in aggregate but it is precisely the class of error this project
exists to demonstrate, so it is handled explicitly rather than approximated.
The gap between the two dates is a weekend, so no trading day is orphaned —
this is asserted by the `no_gaps_in_validity_ranges` test.

---

## 6. Known limitations — stated explicitly

### 6.1 Survivorship bias in the price corpus

The OHLCV dataset covers **current** S&P 500 constituents only. Four seed-table
tickers therefore have no price history and cannot contribute to the anchor
metric:

| Ticker | Why it is absent |
|---|---|
| `TWTR` | Twitter taken private by X Corp, October 2022 — delisted |
| `ATVI` | Activision Blizzard acquired by Microsoft, October 2023 — delisted |
| `TRIP` | TripAdvisor removed from the S&P 500 |
| `ETSY` | Etsy removed from the S&P 500 |

They are **kept in the seed table** because the seed is the transcribed
historical record, not a convenience subset. The pipeline resolves the
dimension against the tradeable universe, and the gap is reported rather than
hidden. This means the measured impact is a **lower bound**: the true effect of
the 2018 restructure was larger than this corpus can show.

### 6.2 Entity discontinuity — the FOXA exclusion

Twenty-First Century Fox was part of the 2018 Consumer Discretionary cohort.
The ticker `FOXA` exists in the price corpus, but its history **begins
2019-03-12** — because the modern Fox Corporation only started trading then,
after Disney acquired 21CF's entertainment assets and the remainder was spun
off.

The `FOXA` of today is a **different legal entity** from the `FOXA` of
September 2018. Treating them as one ticker would silently attribute the new
company's history to the old company's reclassification — the same class of
identity error the project is about, one level down. FOXA is therefore excluded
from the seed table, and the exclusion is asserted by a test rather than left
as a comment.

Ticker reuse of this kind is the standard argument for keying a point-in-time
dimension on a stable entity identifier (CIK, CUSIP, or a warehouse-generated
surrogate) instead of on the ticker string. This project keys on ticker because
the price corpus offers no other join key, and records the consequence here.

### 6.3 Sub-industry coverage is partial by design

`old_gics_sub_industry` and `new_gics_sub_industry` are populated only where a
source document listed them explicitly (S1 for 2018, S5/S7 for 2023). For the
Media & Entertainment cohort that moved as an entire industry group, the
sub-industry columns are left **NULL rather than guessed**. Sector is the
analytical grain of this project; sub-industry is documentation. Inventing
plausible values to fill the column would violate the sourcing standard this
file exists to uphold.

### 6.4 Confidence tiers

| Tier | Basis | Rows |
|---|---|---|
| **Ticker-level document** | Named in a company-by-company change table (S1) | GOOGL, GOOG, META, EA, ATVI, NFLX, TRIP, EBAY, ETSY |
| **Named in analysis** | Named individually in S2/S4/S5 | TTWO, TWTR, DIS, CMCSA, and all 14 of the 2023 cohort |
| **Industry-group rule** | Not named individually; membership follows from the documented wholesale move of the Media & Entertainment industry group (S3) | CHTR, OMC, NWSA, NWS |

The third tier is the weakest and is flagged as such. It does not affect the
headline result: the anchor metric is driven by the Information Technology and
Communication Services sectors, where every contributing ticker sits in tier 1
or tier 2.

---

## 7. Reproducing this table

`sector_history.csv` is committed to the repository because it is the
project's analytical contribution — it cannot be re-downloaded. The other
inputs can:

```bash
make ingest       # re-downloads index membership + snapshot, loads OHLCV
```

If a future GICS review adds an event, the correct change is to **append rows
to the seed** and re-run `dbt build`. The SCD Type 2 logic and every downstream
model handle additional versions per ticker without modification — that
property is asserted by `tests/test_scd_multi_version.py`.
