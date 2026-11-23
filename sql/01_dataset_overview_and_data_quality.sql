-- ============================================================================
-- 01_dataset_overview_and_data_quality.sql
-- Iowa Liquor Sales Analytics (BigQuery)
--
-- Purpose:
--   Profile the public table before any analysis: total volume, date range,
--   distinct entities, and basic data quality checks (nulls, negative or
--   zero sales, duplicate invoice lines).
--
-- Table: bigquery-public-data.iowa_liquor_sales.sales
-- One row is one invoice line: one product bought by one Class E liquor
-- licensee (store) on one date, from the State of Iowa wholesale monopoly.
--
-- Cost note: each query below scans only the columns it names. Run them in
-- the BigQuery sandbox; the free tier covers 1 TB of query processing per
-- month, which is far more than this project needs.
-- ============================================================================

-- 1.1 Headline size of the dataset -------------------------------------------
SELECT
  COUNT(*)                              AS total_rows,
  MIN(date)                             AS first_date,
  MAX(date)                             AS last_date,
  COUNT(DISTINCT store_number)          AS distinct_stores,
  COUNT(DISTINCT item_number)           AS distinct_items,
  COUNT(DISTINCT vendor_number)         AS distinct_vendors,
  COUNT(DISTINCT county)                AS distinct_counties,
  SUM(sale_dollars)                     AS total_sale_dollars,
  SUM(bottles_sold)                     AS total_bottles_sold,
  SUM(volume_sold_liters)               AS total_liters_sold
FROM `bigquery-public-data.iowa_liquor_sales.sales`;

-- 1.2 Null profile on the analytical columns ---------------------------------
SELECT
  COUNTIF(date IS NULL)            AS null_date,
  COUNTIF(store_number IS NULL)    AS null_store_number,
  COUNTIF(category_name IS NULL)   AS null_category_name,
  COUNTIF(vendor_name IS NULL)     AS null_vendor_name,
  COUNTIF(sale_dollars IS NULL)    AS null_sale_dollars,
  COUNTIF(bottles_sold IS NULL)    AS null_bottles_sold,
  COUNT(*)                         AS total_rows
FROM `bigquery-public-data.iowa_liquor_sales.sales`;

-- 1.3 Value sanity: returns and corrections appear as negative lines ---------
SELECT
  COUNTIF(sale_dollars < 0)   AS negative_sales_rows,
  COUNTIF(sale_dollars = 0)   AS zero_sales_rows,
  COUNTIF(bottles_sold <= 0)  AS nonpositive_bottle_rows,
  COUNTIF(volume_sold_liters < 0) AS negative_volume_rows
FROM `bigquery-public-data.iowa_liquor_sales.sales`;

-- 1.4 Duplicate check on the natural key of an invoice line ------------------
SELECT
  COUNT(*) AS duplicate_key_groups
FROM (
  SELECT invoice_and_item_number, item_number, COUNT(*) AS n
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY invoice_and_item_number, item_number
  HAVING n > 1
);

-- 1.5 Rows per year: a quick completeness check of the time coverage ---------
SELECT
  EXTRACT(YEAR FROM date) AS year,
  COUNT(*)                AS rows_in_year,
  MIN(date)               AS first_date_in_year,
  MAX(date)               AS last_date_in_year
FROM `bigquery-public-data.iowa_liquor_sales.sales`
GROUP BY year
ORDER BY year;
