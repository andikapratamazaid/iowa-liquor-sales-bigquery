-- ============================================================================
-- 07_anomaly_detection_inputs.sql
-- Question 5: Which stores and products show unusual monthly sales patterns?
--
-- Approach: build clean monthly series in BigQuery, then score each month
-- against the series' own history with a z-score computed from the mean and
-- standard deviation of the same store or product (STDDEV_POP over a window,
-- or a self join on aggregates). Months with |z| >= 3 are flagged as
-- anomalies for review. The Python step in analysis/anomaly_detection.py
-- applies the same logic to the exported series and plots the worst cases.
--
-- Techniques: DATE_TRUNC, AVG and STDDEV_POP window functions, QUALIFY to
-- keep only flagged rows.
-- ============================================================================

-- 7.1 Monthly sales per store (export this for the Python step) --------------
SELECT
  store_number,
  ANY_VALUE(store_name) AS store_name,
  DATE_TRUNC(date, MONTH) AS month,
  SUM(sale_dollars) AS sale_dollars,
  SUM(bottles_sold) AS bottles_sold,
  COUNT(*) AS invoice_lines
FROM `bigquery-public-data.iowa_liquor_sales.sales`
GROUP BY store_number, month
ORDER BY store_number, month;

-- 7.2 Monthly sales per product item (export this for the Python step) -------
SELECT
  item_number,
  ANY_VALUE(item_description) AS item_description,
  DATE_TRUNC(date, MONTH) AS month,
  SUM(sale_dollars) AS sale_dollars,
  SUM(bottles_sold) AS bottles_sold
FROM `bigquery-public-data.iowa_liquor_sales.sales`
GROUP BY item_number, month
ORDER BY item_number, month;

-- 7.3 In SQL anomaly flags for stores -----------------------------------------
-- A store month is compared with that store's own monthly history. Stores
-- with fewer than 24 months of history are skipped because their mean and
-- standard deviation are not stable enough to score against.
WITH monthly AS (
  SELECT
    store_number,
    DATE_TRUNC(date, MONTH) AS month,
    SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY store_number, month
),
scored AS (
  SELECT
    store_number,
    month,
    sale_dollars,
    AVG(sale_dollars) OVER (PARTITION BY store_number) AS store_month_avg,
    STDDEV_POP(sale_dollars) OVER (PARTITION BY store_number) AS store_month_std,
    COUNT(*) OVER (PARTITION BY store_number) AS months_observed
  FROM monthly
)
SELECT
  store_number,
  month,
  ROUND(sale_dollars, 2) AS sale_dollars,
  ROUND((sale_dollars - store_month_avg) / store_month_std, 2) AS z_score
FROM scored
WHERE months_observed >= 24
  AND store_month_std > 0
  AND ABS((sale_dollars - store_month_avg) / store_month_std) >= 3
ORDER BY ABS(z_score) DESC
LIMIT 100;

-- 7.4 In SQL anomaly flags for products ---------------------------------------
WITH monthly AS (
  SELECT
    item_number,
    DATE_TRUNC(date, MONTH) AS month,
    SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY item_number, month
),
scored AS (
  SELECT
    item_number,
    month,
    sale_dollars,
    AVG(sale_dollars) OVER (PARTITION BY item_number) AS item_month_avg,
    STDDEV_POP(sale_dollars) OVER (PARTITION BY item_number) AS item_month_std,
    COUNT(*) OVER (PARTITION BY item_number) AS months_observed
  FROM monthly
)
SELECT
  item_number,
  month,
  ROUND(sale_dollars, 2) AS sale_dollars,
  ROUND((sale_dollars - item_month_avg) / item_month_std, 2) AS z_score
FROM scored
WHERE months_observed >= 24
  AND item_month_std > 0
  AND ABS((sale_dollars - item_month_avg) / item_month_std) >= 3
ORDER BY ABS(z_score) DESC
LIMIT 100;
