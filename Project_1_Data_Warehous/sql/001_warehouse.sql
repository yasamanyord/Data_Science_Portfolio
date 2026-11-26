-- Schema v1: one fact per immutable source sale (a transaction line, not an order).
-- Monetary values are integer USD cents, never binary floating point.
CREATE TABLE IF NOT EXISTS ingest_run (
    run_id TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL CHECK(length(source_sha256) = 64),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running','committed','replayed','rejected')),
    rows_seen INTEGER NOT NULL DEFAULT 0 CHECK(rows_seen >= 0),
    rows_inserted INTEGER NOT NULL DEFAULT 0 CHECK(rows_inserted >= 0),
    rows_skipped INTEGER NOT NULL DEFAULT 0 CHECK(rows_skipped >= 0),
    error_code TEXT
);
CREATE INDEX IF NOT EXISTS ix_run_hash ON ingest_run(source_sha256, status);
CREATE TABLE IF NOT EXISTS raw_sale (
    raw_id INTEGER PRIMARY KEY,
    source_sale_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL REFERENCES ingest_run(run_id),
    line_number INTEGER NOT NULL CHECK(line_number >= 2),
    payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256) = 64),
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK(quarter BETWEEN 1 AND 4),
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    day INTEGER NOT NULL CHECK(day BETWEEN 1 AND 31)
);
-- Snapshot dimensions retain the exact descriptive attributes reported at sale time.
-- Repeated identical snapshots reuse keys; changed attributes receive a new key.
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY,
    product_id TEXT NOT NULL,
    product_type TEXT NOT NULL,
    category TEXT NOT NULL,
    material TEXT NOT NULL,
    UNIQUE(product_id, product_type, category, material)
);
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    state TEXT NOT NULL,
    country TEXT NOT NULL,
    UNIQUE(customer_id, city, region, state, country)
);
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_key INTEGER PRIMARY KEY,
    raw_id INTEGER NOT NULL UNIQUE REFERENCES raw_sale(raw_id),
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 100000),
    gross_cents INTEGER NOT NULL CHECK(gross_cents BETWEEN 0 AND 10000000000),
    discount_cents INTEGER NOT NULL CHECK(discount_cents BETWEEN 0 AND gross_cents),
    net_cents INTEGER GENERATED ALWAYS AS (gross_cents - discount_cents) STORED,
    currency TEXT NOT NULL CHECK(currency = 'USD')
);
CREATE INDEX IF NOT EXISTS ix_fact_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_product ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS ix_fact_customer ON fact_sales(customer_key);
CREATE VIEW IF NOT EXISTS sales_detail AS
SELECT r.source_sale_id, d.full_date, d.year, d.quarter, d.month, p.product_id,
       p.product_type, p.category, p.material, c.customer_id, c.city,
       c.region, c.state, c.country, s.quantity, s.gross_cents,
       s.discount_cents, s.net_cents, s.currency
FROM fact_sales s
JOIN raw_sale r ON s.raw_id = r.raw_id
JOIN dim_date d ON s.date_key = d.date_key
JOIN dim_product p ON s.product_key = p.product_key
JOIN dim_customer c ON s.customer_key = c.customer_key;
