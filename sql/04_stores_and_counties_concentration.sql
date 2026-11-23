-- ============================================================================
-- 04_stores_and_counties_concentration.sql
-- Question 3: Which stores and counties sell the most, and how concentrated
-- is the market in a small number of large stores?
--
-- Techniques: cumulative share with SUM OVER (ORDER BY ... ROWS frame) to
-- build a concentration curve, RANK for leaderboards, and a Herfindahl
-- style summary computed from store shares.
-- ============================================================================

-- 4.1 Top 25 stores of all time ----------------------------------------------
SELECT
  store_number,
  ANY_VALUE(store_name)   AS store_name,
  ANY_VALUE(city)         AS city,
  ANY_VALUE(county)       AS county,
  SUM(sale_dollars)       AS sale_dollars,
  SUM(bottles_sold)       AS bottles_sold,
  COUNT(*)                AS invoice_lines
FROM `bigquery-public-data.iowa_liquor_sales.sales`
GROUP BY store_number
ORDER BY sale_dollars DESC
LIMIT 25;

-- 4.2 County leaderboard ------------------------------------------------------
SELECT
  county,
  SUM(sale_dollars) AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars) / SUM(SUM(sale_dollars)) OVER (),
    2
  ) AS share_pct,
  COUNT(DISTINCT store_number) AS stores,
  SUM(bottles_sold)            AS bottles_sold
FROM `bigquery-public-data.iowa_liquor_sales.sales`
WHERE county IS NOT NULL
GROUP BY county
ORDER BY sale_dollars DESC
LIMIT 25;

-- 4.3 Concentration curve: cumulative share of the largest stores ------------
WITH store_totals AS (
  SELECT store_number, SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY store_number
),
ranked AS (
  SELECT
    store_number,
    sale_dollars,
    ROW_NUMBER() OVER (ORDER BY sale_dollars DESC) AS store_rank,
    COUNT(*) OVER ()                               AS total_stores,
    SUM(sale_dollars) OVER ()                      AS total_sales,
    SUM(sale_dollars) OVER (
      ORDER BY sale_dollars DESC
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_sales
  FROM store_totals
)
SELECT
  store_rank,
  ROUND(100 * store_rank / total_stores, 2)   AS pct_of_stores,
  ROUND(100 * cumulative_sales / total_sales, 2) AS cumulative_share_pct
FROM ranked
WHERE store_rank IN (10, 25, 50, 100, 200, 500, 1000)
   OR store_rank = total_stores
ORDER BY store_rank;

-- 4.4 How many stores does it take to reach 50 and 80 percent of sales? ------
WITH store_totals AS (
  SELECT store_number, SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  GROUP BY store_number
),
ranked AS (
  SELECT
    ROW_NUMBER() OVER (ORDER BY sale_dollars DESC) AS store_rank,
    COUNT(*) OVER () AS total_stores,
    SUM(sale_dollars) OVER (
      ORDER BY sale_dollars DESC
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(sale_dollars) OVER () AS cumulative_share
  FROM store_totals
)
SELECT
  (SELECT MIN(store_rank) FROM ranked WHERE cumulative_share >= 0.50)
    AS stores_for_50pct,
  (SELECT MIN(store_rank) FROM ranked WHERE cumulative_share >= 0.80)
    AS stores_for_80pct,
  (SELECT total_stores FROM ranked LIMIT 1) AS total_stores;
