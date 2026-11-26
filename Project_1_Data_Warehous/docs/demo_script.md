# Five-minute portfolio demonstration

## 0:00 — Context

"I originally built a star schema and wrote analytical queries for wholesale furniture sales. I upgraded it into a complete data product: a validated incremental ETL pipeline, auditable dimensional warehouse, tested business metrics, read-only dashboard, reproducible tests and an operations handoff."

Explain the grain: one immutable source sale line, not an order. All data is synthetic; no real client deployment is claimed.

## 0:45 — Show working software

Open http://127.0.0.1:8000 after running the default demo. Show net revenue, quantities, sale lines and distinct customers. Select 2025 dates, Bedroom and Canada, then reset. Point out that exact cents are stored, YoY uses the prior calendar month, and amounts are rounded only in the UI.

## 1:45 — Explain architecture

Show the ER diagram and `sql/001_warehouse.sql`. Explain data lineage (source SHA, canonical JSON, raw_id, source sale ID), surrogate dimension snapshots and generated net revenue. Demonstrate one product/customer ID can have different historic descriptive snapshots while business counts use IDs.

## 2:45 — Explain reliability

```bash
python -m warehouse demo
python -m warehouse demo
python -m warehouse runs
python -m warehouse check
```

The second seed replay adds no sale lines. Show 10 passed quality checks; show unit tests for a late-invalid row, duplicates and corrupt fact data. Use `evidence/validation.json` to show independent CSV vs warehouse totals for 5,000 and 50,000 rows and the verified recovery drill. Explain what makes a change safe: deterministic regression baseline + independent source totals + negative controls, not just a visually plausible dashboard.

## 3:45 — Integration and handoff

Open /docs and demonstrate GET /api/report with filters. Export monthly CSV to a fresh filename. Explain read-only parameterized API, Docker/CI, and the Power BI integration guide. Show the runbook so a client team can operate the pipeline without you.

## 4:30 — Be honest about limits

"This is a locally verified synthetic-data build. It won't accept arbitrary SQL, multi-currency or conflicting corrections; a real system needs a signed data contract, authenticated database/BI roles, a managed warehouse, scheduling, operational ownership and tests on client data. The browser and container smoke workflows are configured; I review the actual run results before claiming they passed."

## Interview questions to prepare

- Why choose a star schema? Why use event snapshots instead of overwriting dimensions?
- What happens when a valid row precedes an invalid row in a batch?
- Why is a deduplication check more than a unique primary key?
- How do you test correctness independently from SQL output?
- Why are financial sums integers and ratios nullable?
- How would you migrate from this local warehouse to a managed PostgreSQL or cloud system?
- How does reliable data infrastructure support AI workflows, without letting an LLM invent metrics?
