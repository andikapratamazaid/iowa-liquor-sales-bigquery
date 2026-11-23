-- ============================================================================
-- 03_category_analysis.sql
-- Question 2: Which spirit categories lead the market, and how does their
-- share shift over the years?
--
-- Techniques: share of total with SUM OVER (), a year by category matrix,
-- and conditional aggregation to compare the first and last complete years.
-- ============================================================================

-- 3.1 All time category ranking with share of total sales --------------------
SELECT
  category_name,
  SUM(sale_dollars)       AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars) / SUM(SUM(sale_dollars)) OVER (),
    2
  ) AS share_pct,
  SUM(bottles_sold)       AS bottles_sold,
  SUM(volume_sold_liters) AS liters_sold,
  COUNT(DISTINCT item_number) AS distinct_items
FROM `bigquery-public-data.iowa_liquor_sales.sales`
WHERE category_name IS NOT NULL
GROUP BY category_name
ORDER BY sale_dollars DESC;

-- 3.2 Category share by year (long format, ready for a stacked chart) --------
SELECT
  EXTRACT(YEAR FROM date) AS year,
  category_name,
  SUM(sale_dollars) AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars)
    / SUM(SUM(sale_dollars)) OVER (PARTITION BY EXTRACT(YEAR FROM date)),
    2
  ) AS share_pct_in_year
FROM `bigquery-public-data.iowa_liquor_sales.sales`
WHERE category_name IS NOT NULL
GROUP BY year, category_name
ORDER BY year, sale_dollars DESC;

-- 3.3 Share shift: first complete year versus last complete year -------------
-- Replace the two year literals with the first and last complete years
-- reported by query 01 (rows per year).
-- Caution: the category taxonomy itself changed during the period. Names
-- such as VODKA 80 PROOF and TEQUILA in early years were later replaced by
-- AMERICAN VODKAS and 100% AGAVE TEQUILA, so only compare categories whose
-- names exist in both years, and treat renamed groups with care.
WITH per_year AS (
  SELECT
    EXTRACT(YEAR FROM date) AS year,
    category_name,
    SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE category_name IS NOT NULL
    AND EXTRACT(YEAR FROM date) IN (2012, 2025)
  GROUP BY year, category_name
),
shares AS (
  SELECT
    category_name,
    100 * SUM(IF(year = 2012, sale_dollars, 0))
      / SUM(SUM(IF(year = 2012, sale_dollars, 0))) OVER () AS share_2012,
    100 * SUM(IF(year = 2025, sale_dollars, 0))
      / SUM(SUM(IF(year = 2025, sale_dollars, 0))) OVER () AS share_2025
  FROM per_year
  GROUP BY category_name
)
SELECT
  category_name,
  ROUND(share_2012, 2) AS share_first_year_pct,
  ROUND(share_2025, 2) AS share_last_year_pct,
  ROUND(share_2025 - share_2012, 2) AS share_change_pp
FROM shares
ORDER BY share_change_pp DESC;
