{{
    config(
        materialized='table',
        schema='silver'
    )
}}

-- Reproduces sql/silver/02_build_ticker_universe.sql via ref()/source() instead
-- of a hand-run script. See that file for the full reasoning on the
-- punctuation normalisation and the exclusion policy; this model applies the
-- same logic through dbt's dependency graph.

with price_coverage as (

    select
        ticker,
        min(trade_date) as first_trade_date,
        max(trade_date) as last_trade_date,
        count(*)        as trading_days
    from {{ source('bronze', 'daily_prices') }}
    group by ticker

),

snapshot_normalised as (

    select
        replace(ticker, '.', '-') as ticker,
        ticker                    as snapshot_ticker,
        security_name,
        gics_sector,
        gics_sub_industry
    from {{ source('bronze', 'sp500_current_snapshot') }}

)

select
    p.ticker,
    s.snapshot_ticker,
    s.security_name,
    s.gics_sector          as current_gics_sector,
    s.gics_sub_industry    as current_sub_industry,
    p.first_trade_date,
    p.last_trade_date,
    p.trading_days
from price_coverage as p
inner join snapshot_normalised as s using (ticker)
where s.gics_sector is not null
  and not exists (
      select 1
      from {{ source('bronze', 'excluded_entities') }} as e
      where e.ticker = p.ticker
  )
