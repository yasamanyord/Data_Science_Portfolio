"""Parameterized, aggregate-only analytics and spreadsheet-safe BI export."""
import csv
from datetime import date
from pathlib import Path

from .db import connect, assert_version


def filter_clause(start=None, end=None, category=None, country=None):
    if start and end and start > end:
        raise ValueError("start date must not be after end date")
    conditions, params = [], []
    for name, operator, value in (
        ("full_date", ">=", start), ("full_date", "<=", end),
        ("category", "=", category), ("country", "=", country),
    ):
        if value is not None:
            conditions.append(f"{name} {operator} ?")
            params.append(value.isoformat() if isinstance(value, date) else value)
    return (" WHERE " + " AND ".join(conditions) if conditions else ""), params


def dicts(cursor):
    return [dict(row) for row in cursor]


def report(path, start=None, end=None, category=None, country=None):
    where, params = filter_clause(start, end, category, country)
    # Single read transaction gives one consistent snapshot across all queries.
    with connect(path, readonly=True) as db:
        assert_version(db)
        db.execute("BEGIN")
        summary = dict(db.execute(f"""
            SELECT COUNT(*) AS sales, COALESCE(SUM(quantity),0) AS units,
                   COALESCE(SUM(gross_cents),0) AS gross_cents,
                   COALESCE(SUM(discount_cents),0) AS discount_cents,
                   COALESCE(SUM(net_cents),0) AS net_cents,
                   COUNT(DISTINCT customer_id) AS customers,
                   COUNT(DISTINCT product_id) AS products
            FROM sales_detail{where}""", params).fetchone())
        repeat = db.execute(f"""SELECT COUNT(*) FROM (
            SELECT customer_id FROM sales_detail{where}
            GROUP BY customer_id HAVING COUNT(*) > 1)""", params).fetchone()[0]
        summary["repeat_customers"] = repeat
        summary["discount_pct"] = round(100 * summary["discount_cents"] / summary["gross_cents"], 2) if summary["gross_cents"] else None
        summary["avg_sale_cents"] = round(summary["net_cents"] / summary["sales"]) if summary["sales"] else None
        monthly = dicts(db.execute(f"""
            WITH m AS (SELECT substr(full_date,1,7) AS month,
                SUM(net_cents) AS net_cents, SUM(quantity) AS units, COUNT(*) AS sales
                FROM sales_detail{where} GROUP BY 1)
            SELECT m.*, prev.net_cents AS prior_year_net_cents,
            CASE WHEN prev.net_cents > 0 THEN
                ROUND(100.0 * (m.net_cents - prev.net_cents) / prev.net_cents, 2)
                END AS yoy_pct
            FROM m LEFT JOIN m AS prev ON prev.month = strftime('%Y-%m',m.month||'-01','-1 year')
            ORDER BY m.month""", params))
        categories = dicts(db.execute(f"""SELECT category, SUM(net_cents) AS net_cents,
            SUM(quantity) AS units FROM sales_detail{where} GROUP BY category
            ORDER BY net_cents DESC, category LIMIT 100""", params))
        regions = dicts(db.execute(f"""SELECT country, region, SUM(net_cents) AS net_cents,
            COUNT(*) AS sales FROM sales_detail{where} GROUP BY country, region
            ORDER BY net_cents DESC, country, region LIMIT 20""", params))
        products = dicts(db.execute(f"""
            WITH totals AS (SELECT product_type, SUM(quantity) AS units,
                SUM(net_cents) AS net_cents FROM sales_detail{where} GROUP BY product_type),
            ranked AS (SELECT *, DENSE_RANK() OVER(ORDER BY units DESC) AS units_rank FROM totals)
            SELECT * FROM ranked ORDER BY units_rank, product_type LIMIT 10""", params))
        options = {
            "categories": [r[0] for r in db.execute("SELECT DISTINCT category FROM dim_product ORDER BY category LIMIT 250")],
            "countries": [r[0] for r in db.execute("SELECT DISTINCT country FROM dim_customer ORDER BY country LIMIT 250")],
        }
        return {"currency": "USD", "summary": summary, "monthly": monthly,
                "categories": categories, "regions": regions, "products": products, "options": options}


def runs(path, limit=20):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    with connect(path, readonly=True) as db:
        assert_version(db)
        return dicts(db.execute("""SELECT run_id, started_at, finished_at, status, rows_seen,
             rows_inserted, rows_skipped, error_code FROM ingest_run
             ORDER BY started_at DESC, rowid DESC LIMIT ?""", (limit,)))


def spreadsheet_cell(value):
    # BI export is aggregate only; avoid CSV spreadsheet formula execution.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_monthly(path, destination):
    destination = Path(destination)
    if destination.resolve() == Path(path).resolve():
        raise ValueError("export must not overwrite warehouse database")
    rows = report(path)["monthly"]
    fields = ["month", "net_cents", "units", "sales", "prior_year_net_cents", "yoy_pct"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: spreadsheet_cell(row[k]) for k in fields})
    return len(rows)
