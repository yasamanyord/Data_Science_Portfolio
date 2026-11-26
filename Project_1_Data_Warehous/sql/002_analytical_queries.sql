-- Run against the upgraded warehouse, e.g. with SQLite CLI:
-- sqlite3 runtime/warehouse.sqlite3 < sql/002_analytical_queries.sql
-- Currency is explicitly USD; amounts below are exact cents.

-- Q1: City, type and year-month performance (no accidental cross-year merge).
SELECT country, city, product_type, substr(full_date,1,7) AS year_month,
       SUM(quantity) AS units, SUM(gross_cents) AS gross_cents,
       SUM(discount_cents) AS discount_cents, SUM(net_cents) AS net_cents
FROM sales_detail GROUP BY country, city, product_type, year_month
ORDER BY year_month, country, city, product_type;

-- Q2: Per-sale averages by country, material and year.
SELECT country, material, year, COUNT(*) AS sale_count,
       ROUND(AVG(quantity),2) AS avg_units, ROUND(AVG(net_cents),2) AS avg_net_cents
FROM sales_detail GROUP BY country, material, year ORDER BY year,country,material;

-- Q3: Top five ranks per May year (ties may produce more than five rows).
WITH totals AS (
    SELECT year, product_type, SUM(quantity) AS units
    FROM sales_detail WHERE month=5 GROUP BY year,product_type
), ranked AS (
    SELECT *, DENSE_RANK() OVER(PARTITION BY year ORDER BY units DESC) AS ranking
    FROM totals
)
SELECT * FROM ranked WHERE ranking<=5 ORDER BY year,ranking,product_type;

-- Q4: Year-over-year monthly revenue using exact prior calendar month.
WITH totals AS (
    SELECT substr(full_date,1,7) AS month,SUM(net_cents) AS net_cents
    FROM sales_detail GROUP BY 1
)
SELECT t.*, p.net_cents AS prior_year_net_cents,
       CASE WHEN p.net_cents>0 THEN ROUND(100.0*(t.net_cents-p.net_cents)/p.net_cents,2) END AS yoy_pct
FROM totals t LEFT JOIN totals p ON p.month=strftime('%Y-%m',t.month||'-01','-1 year')
ORDER BY t.month;

-- Q5: Share of revenue for each category; NULL if total is zero.
WITH totals AS (SELECT category,SUM(net_cents) AS net_cents FROM sales_detail GROUP BY category)
SELECT *, ROUND(100.0*net_cents/NULLIF(SUM(net_cents) OVER(),0),2) AS share_pct
FROM totals ORDER BY net_cents DESC,category;

-- Q6: Repeat customers across distinct source sale lines.
SELECT customer_id,COUNT(*) AS sales,SUM(net_cents) AS net_cents
FROM sales_detail GROUP BY customer_id HAVING COUNT(*)>1 ORDER BY sales DESC,customer_id;
