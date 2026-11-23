-- ============================================================================
-- 06_vendor_share.sql
-- Question 6: Which vendors supply the Iowa market, and how dependent is
-- the market on the largest few?
--
-- Note on roles: vendors are the suppliers that sell spirits to the State
-- of Iowa; stores buy from the state. Vendor share therefore measures
-- supply side concentration of the whole state market.
--
-- Techniques: share of total, cumulative share for the top vendors, and a
-- Herfindahl Hirschman Index (HHI) computed from squared percentage shares.
-- HHI above 2500 is conventionally read as a highly concentrated market.
-- ============================================================================

-- 6.1 Top 20 vendors by sales --------------------------------------------------
SELECT
  vendor_number,
  ANY_VALUE(vendor_name) AS vendor_name,
  SUM(sale_dollars)      AS sale_dollars,
  ROUND(
    100 * SUM(sale_dollars) / SUM(SUM(sale_dollars)) OVER (),
    2
  ) AS share_pct,
  SUM(bottles_sold)          AS bottles_sold,
  COUNT(DISTINCT item_number) AS distinct_items,
  COUNT(DISTINCT store_number) AS stores_supplied
FROM `bigquery-public-data.iowa_liquor_sales.sales`
WHERE vendor_name IS NOT NULL
GROUP BY vendor_number
ORDER BY sale_dollars DESC
LIMIT 20;

-- 6.2 Cumulative share of the top 1, 3, 5 and 10 vendors ----------------------
WITH vendor_totals AS (
  SELECT vendor_number, SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE vendor_name IS NOT NULL
  GROUP BY vendor_number
),
ranked AS (
  SELECT
    ROW_NUMBER() OVER (ORDER BY sale_dollars DESC) AS vendor_rank,
    COUNT(*) OVER () AS total_vendors,
    SUM(sale_dollars) OVER (
      ORDER BY sale_dollars DESC
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(sale_dollars) OVER () AS cumulative_share
  FROM vendor_totals
)
SELECT
  vendor_rank,
  ROUND(100 * cumulative_share, 2) AS cumulative_share_pct,
  total_vendors
FROM ranked
WHERE vendor_rank IN (1, 3, 5, 10, 20)
ORDER BY vendor_rank;

-- 6.3 Market concentration: HHI over vendor shares ----------------------------
WITH vendor_totals AS (
  SELECT
    vendor_number,
    SUM(sale_dollars) AS sale_dollars
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE vendor_name IS NOT NULL
  GROUP BY vendor_number
),
shares AS (
  SELECT
    100 * sale_dollars / SUM(sale_dollars) OVER () AS share_pct
  FROM vendor_totals
)
SELECT
  ROUND(SUM(POW(share_pct, 2)), 0) AS hhi,
  COUNT(*) AS vendors
FROM shares;

-- 6.4 Vendor share trend for the top 5 vendors --------------------------------
WITH top_vendors AS (
  SELECT vendor_number
  FROM `bigquery-public-data.iowa_liquor_sales.sales`
  WHERE vendor_name IS NOT NULL
  GROUP BY vendor_number
  ORDER BY SUM(sale_dollars) DESC
  LIMIT 5
)
SELECT
  EXTRACT(YEAR FROM s.date) AS year,
  s.vendor_number,
  ANY_VALUE(s.vendor_name) AS vendor_name,
  SUM(s.sale_dollars) AS sale_dollars,
  ROUND(
    100 * SUM(s.sale_dollars)
    / SUM(SUM(s.sale_dollars)) OVER (PARTITION BY EXTRACT(YEAR FROM s.date)),
    2
  ) AS share_pct_in_year
FROM `bigquery-public-data.iowa_liquor_sales.sales` AS s
WHERE s.vendor_number IN (SELECT vendor_number FROM top_vendors)
GROUP BY year, s.vendor_number
ORDER BY year, sale_dollars DESC;
