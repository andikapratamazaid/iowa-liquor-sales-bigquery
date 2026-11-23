-- ============================================================================
-- 02_trend_and_seasonality.sql
-- Question 1: How do sales evolve over time, and is there seasonality?
--
-- Techniques: DATE_TRUNC aggregation, window functions for year over year
-- growth (LAG) and a 3 month moving average (AVG OVER with a ROWS frame),
-- and a month of year profile that averages each calendar month across all
-- complete years.
-- ============================================================================

-- 2.1 Yearly trend with year over year growth --------------------------------
WITH yearly AS (
  SELECT
    EXTRACT(YEAR FROM date) AS year,
    SUM(sale_dollars)       AS sale_dollars,
    SUM(bottles_sold)       AS bottles_sold,
    SUM(volume_sold_liters) AS liters_sold,
    COUNT(*)                AS invoice_lines
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY year
)
SELECT
  year,
  sale_dollars,
  ROUND(
    100 * (sale_dollars - LAG(sale_dollars) OVER (ORDER BY year))
    / LAG(sale_dollars) OVER (ORDER BY year),
    2
  ) AS yoy_growth_pct,
  bottles_sold,
  liters_sold,
  invoice_lines
FROM yearly
ORDER BY year;

-- 2.2 Monthly series with a 3 month moving average ---------------------------
WITH monthly AS (
  SELECT
    DATE_TRUNC(date, MONTH) AS month,
    SUM(sale_dollars)       AS sale_dollars,
    SUM(bottles_sold)       AS bottles_sold
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY month
)
SELECT
  month,
  sale_dollars,
  AVG(sale_dollars) OVER (
    ORDER BY month
    ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
  ) AS sale_dollars_3mo_avg,
  bottles_sold
FROM monthly
ORDER BY month;

-- 2.3 Seasonality profile: average sales per calendar month ------------------
-- Restricted to complete calendar years so a partial current year does not
-- distort the profile. The seasonality index expresses each month against
-- the average month (100 = an exactly average month).
WITH complete_years AS (
  SELECT EXTRACT(YEAR FROM date) AS year
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY year
  HAVING MIN(date) <= DATE(year, 1, 5) AND MAX(date) >= DATE(year, 12, 25)
),
monthly AS (
  SELECT
    EXTRACT(MONTH FROM date) AS month_of_year,
    SUM(sale_dollars)        AS sale_dollars,
    COUNT(DISTINCT EXTRACT(YEAR FROM date)) AS years_observed
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE EXTRACT(YEAR FROM date) IN (SELECT year FROM complete_years)
  GROUP BY month_of_year
)
SELECT
  month_of_year,
  sale_dollars / years_observed AS avg_sale_dollars,
  ROUND(
    100 * (sale_dollars / years_observed)
    / (SUM(sale_dollars / years_observed) OVER () / 12),
    1
  ) AS seasonality_index
FROM monthly
ORDER BY month_of_year;
