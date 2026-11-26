# Client discovery, acceptance and production-readiness assessment

## Discovery questions

- What decisions should the warehouse support (inventory demand, regional sales, discount strategy)? Who signs off on metric definitions?
- What is the source grain, stable identifier, correction/refund process, currency, date/time zone, expected cadence and volume?
- Which product and customer attributes change? Is history at sale time required, or should reports use latest master data?
- Which fields are necessary? What information is confidential? Who may access aggregates and source data?
- How fresh must data be? How will source totals, incomplete deliveries and failed jobs be reconciled?
- Who owns the data contract, BI dashboard, approvals, alerts, backups and incident response?

## Acceptance checklist

| Requirement | Acceptance evidence | State |
|---|---|---|
| Repeatable local installation | CLI demo run, Python requirements, Windows launcher | Implemented; CLI verified, launcher not run on Windows |
| Preserve original project | Three legacy scripts and 100-row migration test | Verified |
| Accurate KPIs | Independent raw CSV totals, known fixture and legacy amounts | Verified |
| No duplicate revenue | Same file, mixed overlap, concurrent file replay tests | Verified |
| Reject bad events atomically | Invalid late row + conflicting-ID rollback tests | Verified |
| History preserved | Snapshot dimension tests | Verified |
| Read-only API and error handling | 12 API tests, live localhost smoke | Verified |
| Quality gate | Ten checks, tampering negative control, baseline regression | Verified |
| Recovery | Online backup and equal restored totals | Verified |
| Scale probe | 5,000 and 50,000 synthetic rows | Verified locally, not a load/concurrency SLA |
| Browser UX | Browser smoke and responsive CSS | Verified in hosted CI on desktop/mobile; real screenshots included |
| Container package | Non-root Dockerfile, Compose health and smoke workflow | Verified hosted CI container build, startup and API smoke |
| BI handoff | Monthly aggregate CSV export and Power BI guide | Export verified; actual Power BI report not created |
| Company deployment | Managed service, client-approved real sources, access and compliance review | Not implemented / no client validated |
| Governance & operations | Ownership, signed source definitions, retention, disaster recovery, monitoring | Requires real company acceptance |

## Risk register

| Risk | Mitigation in portfolio | Before actual deployment |
|---|---|---|
| Incorrect metrics | Explicit contract and independent reconciliation; no cost/FX claims | Business approval, source-system total comparison |
| Duplicate events | Source identity, canonical payload hashes, atomic loader | Multi-source namespace and correction contract |
| Data breach | Local-only synthetic data; no demographic or contact fields; no API writes | SSO/RBAC, network isolation, encrypted data, permissions audit, secret rotation, retention |
| Unavailable or partial delivery | Run history and source hash; transactional batches | Intake manifest, freshness SLAs, scheduler retries/alerts, incident ownership |
| SQLite limits | WAL, bounded source, consistent read transactions | Benchmark PostgreSQL/cloud warehouse, implement concurrent load strategy |
| Silent regression | Golden fixture, baseline comparisons and independent quality gate | Approved change control, integration and load tests, staged release |

## Production roadmap (not claimed complete)

1. **Pilot discovery**: get a signed source data dictionary, canonical IDs, amount semantics and actual permissions. Define freshness, volume, success and recovery objectives.
2. **Source adapter**: use approved ERP/CRM/export API or object storage with explicit namespace, schema evolution, retry and ingestion manifest. Add integration tests in a sandbox.
3. **Managed storage**: migrate the logical layers to PostgreSQL or an appropriate cloud analytical warehouse; deploy schema migrations, independently test SQL dialect, isolation and indexing. Add full date spine and governed master-data semantics as needed.
4. **Access and privacy**: implement RBAC/SSO, tenant isolation if applicable, network segmentation, encrypted transports/storage, read-only BI identities and audit retention. Protect raw event data; perform security review.
5. **Orchestration**: implement scheduled ingestion/data freshness with Airflow, Dagster, managed jobs or another approved scheduler; alert on failed loads and missing source batches. No scheduler infrastructure is bundled.
6. **BI and rollout**: test Power BI measures against signed finance totals, choose refresh strategy, benchmark representative volume and stakeholder acceptance; conduct restore drill and document support ownership.
7. **Optional bounded AI extension**: provide a natural-language analyst interface limited to approved metric endpoints with citations/filters, read-only permissions, human review and golden-question evals. Not part of this version.

Only once these steps are verified may the project be described as deployed to a real company. Local demo results are portfolio proof of engineering, not revenue impact or production usage claims.
