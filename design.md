# Iowa Liquor Sales — BigQuery Project Design (DRAFT, for approval before build)

Status: design only. Chosen by Andika 22 Nov 2026, 14:49 WIB, from the 4 BigQuery
candidates (he picked "Iowa Liquor Sales (skala big data)").
Per his fixed project rhythm: design in chat first -> build -> ZIP -> publish to
GitHub ONLY when he explicitly says so. Do not publish from this draft.

## Why this one
- Direct BigQuery-at-scale proof for his Data Analyst positioning (Upwork /
  Freelancer, USD 20/hr): SQL over tens of millions of rows, not a small CSV.
- Distinct from his existing portfolio: no other project uses BigQuery public
  data or a US retail dataset. Portfolio standing 17 Nov 2026: Data 17, AI 9,
  Web 4, Agri 3 = 33 projects total. This would be Data #18 / total #34.
- Free: BigQuery sandbox, no credit card, no billing account.

## Dataset — verified facts (22 Nov 2026)
- Table: `bigquery-public-data.iowa_liquor_sales.sales`
- Source: Iowa Class "E" liquor licensees, spirits purchases by product and
  date, from 1 Jan 2012 to current (Google Cloud docs).
- Columns used in prior public work (24 columns total): invoice_and_item_number,
  date, store_number, store_name, city, county, vendor_name, category_name,
  item_description, bottles_sold, volume_sold_liters, sale_dollars,
  state_bottle_cost, state_bottle_retail.
  TO VERIFY before writing final SQL: run INFORMATION_SCHEMA query in console
  and confirm exact column names/types — do not trust memory.
- Size snapshot (older, NOT current): 24,229,431 rows / 6.4 GB in a 2022 write-up.
  Current row count is larger (data runs to current). First query must be a
  COUNT(*) + MIN/MAX(date) metadata check; never quote the 24.2M figure as today's size.
- Google also uses this table in its own BQML tutorials (forecasting, ARIMA_PLUS,
  contribution analysis), including the note that bottles sold rose from
  1.3-1.5M in 2012 to ~2.6M in recent years, with Oct/Dec and May/Jun peaks and
  Jan/Feb troughs — useful as a sanity check, not as a result to copy.

## Free-tier guardrails (verified, Google Cloud docs)
- Sandbox: no credit card, no billing account; same free tier as billed accounts:
  1 TB query data processed/month, 10 GB active storage.
- Sandbox limits that matter: tables/partitions expire after 60 days; 10 GB
  storage is a lifetime allowance (deleting does not refund it); DML, streaming
  and Data Transfer Service are not included.
- Cost discipline for this project:
  1. Never SELECT * on the full table. Select only needed columns.
  2. Always filter by date first; check the validator's "This query will process
     X" estimate before Run.
  3. Aggregate in BigQuery, export only small aggregate CSVs (KBs) for charts —
     never download the raw table (GBs, and it would burn the 10 GB storage).
  4. Keep each exploratory query to a few GB at most; the full-table scan of the
     core columns is small vs the 1 TB monthly quota, but repeated full scans add up.

## Analysis plan — 6 questions (Q1-Q6)
Scope: full trend 2012-present for Q1; deep dive on the last 5 complete calendar
years for Q2-Q6 (exact years fixed after the MIN/MAX(date) check — if the latest
complete year is 2025, deep dive = 2021-2025; if 2024, then 2020-2024).
- Q1 Trend & scale: monthly/yearly sale_dollars, bottles_sold, volume_sold_liters.
  Seasonality (Oct/Dec peaks, Jan/Feb troughs) + COVID 2020-21 as stated confounder.
- Q2 Category mix: sale_dollars share by category_name (vodka, whiskey, tequila,
  etc.); which categories grew fastest in the deep-dive window; margin proxy
  (sale_dollars minus state_bottle_cost x bottles_sold) by category.
- Q3 Geography: top cities/counties by sale_dollars; sales per store; Des Moines
  vs rest (prior work found Des Moines ~$50M in its window — re-measure, do not copy).
- Q4 Stores & vendors: top 20 stores and top 10 vendors by sale_dollars; vendor
  concentration (share of top 5 vendors); store count trend.
- Q5 Products: top 20 item_description by sale_dollars and by bottles_sold;
  price per bottle (sale_dollars / bottles_sold) distribution; premium vs volume leaders.
- Q6 Anomalies & data quality: nulls by key column, duplicate invoice_and_item_number,
  negative/zero sale_dollars or bottles_sold, single-day spikes vs monthly median.
  Report honestly; never fill gaps.

## Deliverables (mirroring MarketShock / StreamGuard structure)
- README.md — question, key results table (real numbers only), charts embedded
- sql/ — q1_trend.sql ... q6_anomalies.sql + 00_metadata_check.sql, each with
  its processed-bytes note from the validator
- data/ — exported aggregate CSVs only (small), with query + run date in header
- charts/ — real charts generated from the exported aggregates (per his 17 Nov
  rule: real results/screenshots, never hand-edited visuals)
- dashboard/ — Looker Studio link or static HTML dashboard from the same aggregates
- docs/findings_report.md — findings, confounders (COVID, category-definition
  changes, store openings/closures), limitations
- tests/ — reconciliation checks (totals across queries agree; row counts match
  metadata check; no fabricated rows)

## What Andika needs to decide (one line each)
1. Approve this design + the deep-dive window rule above, or change the window.
2. Confirm he will run the queries himself in his own BigQuery console (sandbox,
   his Google account) — Muse cannot run them from here and must not ask for
   his Google login.
3. After build + ZIP, he decides separately whether to publish to GitHub.

## Open / unverified
- Exact current row count, date range, column list — first metadata query.
- Latest complete year for the deep dive — depends on that check.
- Whether Looker Studio (free, same Google account) or a static HTML dashboard
  is preferred — ask at build stage, not now.
