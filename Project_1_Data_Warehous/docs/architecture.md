# Architecture and engineering decisions

## Scope and context

The original wholesale furniture exercise uses `Sales`, `Furniture`, `Customer`, and `Time` tables. The upgrade adds an operational pipeline around the same star schema, rather than replacing the business problem. The original four tables and three scripts are preserved in the project root.

### Components

| Layer | Files | Responsibility |
|---|---|---|
| Source | `warehouse/generate.py`, `warehouse/legacy.py` | Seeded synthetic CSV or explicit one-time legacy migration |
| Contract | `warehouse/contract.py` | Normalize, validate and hash source events; fail closed |
| Storage | `sql/001_warehouse.sql`, `warehouse/db.py` | Versioned DDL; transactional ingestion; dimension snapshots and fact line lineage |
| Mart | `sales_detail` view, `warehouse/analytics.py`, `sql/002_analytical_queries.sql` | Consistent filtered reporting; parameterized SQL |
| Quality | `warehouse/quality.py`, `evidence/validate.py` | Reconcile source, fact and mart; integrity and negative tests |
| Access | `warehouse/api.py`, `static/` | Read-only local analytics and operational visibility |
| Operations | CLI, Docker Compose, CI | Reproducibility, release gate, validation artifacts and backups |

## Data flow

1. Initialize only an empty dedicated SQLite database or a supported schema version. DDL identifies schema 1 through `PRAGMA user_version`.
2. Compute SHA-256 across the bounded file; add a separately committed `running` audit record.
3. Acquire an immediate transaction to serialize writers. A previously committed identical file is replayed. Otherwise validate and transform the records.
4. Reuse or create date/product/customer keys; store canonical JSON and hash per unique source sale; create one fact with exact amounts.
5. Commit the run status and all inserted rows together. Contract or SQLite write failure rolls back the batch and attempts to mark its audit row rejected. Disk/device failures may prevent that final audit update.
6. The quality gate checks committed data independently. Queries use a read-only, consistent snapshot and expose aggregate results only.
7. For recovery, use SQLite online backup, validate the copied file, and point the API/CLI to it.

The hash is useful for deduplication and tamper detection, not a digital signature. Raw canonical JSON preserves normalized data and source file hash/line number, not the original unnormalized CSV bytes. A business must separately retain approved raw delivery files under its own retention policy. Audit records are not cryptographically immutable; a privileged database writer can alter them.

## Key modeling decisions

- **Grain before measures:** one immutable ID for each source sale line. The source does not provide order or invoice IDs; do not label sale-line count as order count.
- **Event snapshots:** product and customer keys represent attributes included in the event. New attributes get new surrogate keys; existing facts do not change. This supports out-of-order event delivery without claiming temporal master-data validity ranges.
- **Dates:** month is an integer, year and quarter are explicit, full date is ISO; no accidental aggregation of May across several years. Only observed dates are stored. A managed BI deployment should have a complete date spine and define missing-vs-zero semantics.
- **Amount representation:** one currency, integer cents (no FX, no floats for ledger sums); net is a generated value. Derived ratios can be rounded.
- **Conflict semantics:** exactly matching immutable IDs are idempotent, changed payloads are rejected. Refunds, corrections and cancellation events require a separate approved event contract, not overwriting history.
- **Workload:** SQLite WAL, indexes on fact foreign keys, short bounded batches and serialization fit this single-machine portfolio build. Managed PostgreSQL or an analytical warehouse is the scale-out path; benchmark with a representative workload before claiming capacity.
- **No AI magic:** reporting logic is deterministic and auditable. Any later natural-language interface must use allowlisted, read-only predefined metrics and show sources, never execute unrestricted generated SQL.

## Security boundary

The API is local and has no authentication. It runs read-only at the database connection layer, with parameterized filters and no ingestion/write route. Bind the host to loopback; Compose uses an internal listener with a loopback-only published port. Use only synthetic data. Raw data includes source IDs and geography even without names or contacts. No actual client records, credentials or personal demographic fields should be committed or served.

## Technical debt and migration plan

The current schema is intentionally narrow. Multi-currency, returns, costs/profit, invoice grain, complete date calendar, source correction events, dimension effective dates, data access controls, privacy deletion, source-system CDC, and multi-tenant segregation need business definitions and separate regression tests. Do not claim these features currently exist.
