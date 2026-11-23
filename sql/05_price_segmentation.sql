-- ============================================================================
-- 05_price_segmentation.sql
-- Question 4: How does price per liter differ by category, and how much of
-- the market is premium versus value?
--
-- Definition: price per liter of a group of sales is total sale dollars
-- divided by total liters, which weights every liter equally and avoids the
-- distortion of averaging per bottle prices. Segments are defined on the
-- price per liter of individual invoice lines:
--   Value   : under 15 USD per liter
--   Core    : 15 to 25 USD per liter
--   Premium : 25 to 40 USD per liter
--   Super premium : 40 USD per liter and above
--
-- Techniques: APPROX_QUANTILES for robust medians and percentiles at scale,
-- SAFE_DIVIDE, and CASE based segmentation with share of total.
-- ============================================================================

-- 5.1 Price per liter distribution by category -------------------------------
SELECT
  category_name,
  COUNT(*) AS invoice_lines,
  ROUND(SUM(sale_dollars) / SUM(volume_sold_liters), 2) AS weighted_price_per_liter,
  ROUND(
    APPROX_QUANTILES(
      SAFE_DIVIDE(sale_dollars, volume_sold_liters), 100
    )[OFFSET(50)],
    2
  ) AS median_line_price_per_liter,
  ROUND(
    APPROX_QUANTILES(
      SAFE_DIVIDE(sale_dollars, volume_sold_liters), 100
    )[OFFSET(25)],
    2
  ) AS p25_line_price_per_liter,
  ROUND(
    APPROX_QUANTILES(
      SAFE_DIVIDE(sale_dollars, volume_sold_liters), 100
    )[OFFSET(75)],
    2
  ) AS p75_line_price_per_liter
FROM `bigquery-public-data.iowa_liquor_sales.sales`
WHERE category_name IS NOT NULL
  AND volume_sold_liters > 0
GROUP BY category_name
ORDER BY weighted_price_per_liter DESC;

-- 5.2 Segment mix overall and by year ----------------------------------------
WITH lines AS (
  SELECT
    EXTRACT(YEAR FROM date) AS year,
    CASE
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 15 THEN 'Value (<15)'
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 25 THEN 'Core (15-25)'
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 40 THEN 'Premium (25-40)'
      ELSE 'Super premium (40+)'
    END AS segment,
    sale_dollars,
    volume_sold_liters
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE volume_sold_liters > 0 AND sale_dollars > 0
)
SELECT
  year,
  segment,
  SUM(sale_dollars) AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars) / SUM(SUM(sale_dollars)) OVER (PARTITION BY year),
    2
  ) AS share_pct_in_year
FROM lines
GROUP BY year, segment
ORDER BY year, segment;

-- 5.3 Segment mix by category -------------------------------------------------
WITH lines AS (
  SELECT
    category_name,
    CASE
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 15 THEN 'Value (<15)'
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 25 THEN 'Core (15-25)'
      WHEN SAFE_DIVIDE(sale_dollars, volume_sold_liters) < 40 THEN 'Premium (25-40)'
      ELSE 'Super premium (40+)'
    END AS segment,
    sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE category_name IS NOT NULL
    AND volume_sold_liters > 0 AND sale_dollars > 0
)
SELECT
  category_name,
  segment,
  SUM(sale_dollars) AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars)
    / SUM(SUM(sale_dollars)) OVER (PARTITION BY category_name),
    2
  ) AS share_pct_in_category
FROM lines
GROUP BY category_name, segment
ORDER BY category_name, segment;
