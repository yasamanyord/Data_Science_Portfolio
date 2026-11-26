# Operator runbook

Use only local synthetic data. All commands are run from the project directory. Activate the virtual environment first.

## Normal operations

1. `python -m warehouse init`
2. Receive a source file through your approved internal intake; never execute its contents as SQL. For the demo, generate a fresh CSV with `generate`.
3. `python -m warehouse pipeline runtime/incoming.csv` (ingest and validate; nonzero exit on failure).
4. Save the CLI output and source file hash in the approved operational system. Inspect `python -m warehouse runs`.
5. When quality passes, publish an aggregate export to a **new filename** with `python -m warehouse export runtime/monthly-YYYY-MM-DD.csv`.
6. Start dashboard with `python -m uvicorn warehouse.api:app --host 127.0.0.1 --port 8000`; check /health and /api/quality.

Repeat steps 2–5 for each batch. A scheduler can run the CLI with a dedicated OS account and a dedicated database (`--db` before the subcommand). In a real deployment use an authenticated orchestrator and an externally controlled file archive, alerting, log rotation, and retention schedule. Do not run a cron job that blindly considers a nonzero exit a success.

## Failure modes and recovery

| Symptom | Action |
|---|---|
| Schema mismatch / invalid CSV | Quarantine the source outside the repo, check the v1 contract and ask the source owner for a corrected full batch. Never patch facts by hand. |
| Conflicting sale ID | Compare original approved event with corrected source owner record. The current contract rejects changed ID payloads; design a governed correction event before importing. |
| Replayed/overlapping batch | Confirm zero new duplicate facts and inspect skipped counts; often expected. |
| SQLite locked | Check concurrent writes and permissions. Let the active writer finish. Retry the exact source safely. |
| Run stuck in running | It can be transient during a live load; after verifying no active process, stop publication, inspect audit and DB integrity. A process crash/disk full can leave an orphan. Recover from verified backup and replay accepted batches or have a DB administrator perform documented repair. |
| Quality gate fails after commit | Stop reporting/export, keep evidence, isolate the affected DB, investigate with read-only queries. Do not assume earlier commits rolled back. |
| /health returns 503 | Check path and schema; set WAREHOUSE_DB to the intended DB; initialize a new dedicated file only if appropriate. |
| Dashboard filter shows no results | Check date/category/country filters. A valid empty selection returns zero totals and null ratios. |

Rejected audit rows retain safe error codes and counts of parsed/attempted valid rows; they do not retain the invalid event payload. Over-limit byte files are rejected before a full hash/audit; log the source intake failure outside the warehouse. Running status may briefly make quality fail while a load is in progress. No real service-level guarantees have been measured.

## Backup and restore drill

```bash
python -m warehouse backup runtime/verified-backup.sqlite3
python -m warehouse --db runtime/verified-backup.sqlite3 check
python -m warehouse --db runtime/verified-backup.sqlite3 report
```

The backup uses SQLite's online backup API rather than copying a live WAL database. The backup is checked for integrity and reconciliation. It refuses to overwrite an existing file. To restore, stop writers, keep the original database intact, validate a separate copy of the verified backup and point `WAREHOUSE_DB` at that copy (PowerShell: `$env:WAREHOUSE_DB="runtime/restored.sqlite3"`; Bash: `export WAREHOUSE_DB=runtime/restored.sqlite3`). Re-run tests and compare source high-water mark, run history and KPIs before returning to service. Test actual recovery time and loss tolerance with client data before declaring backup SLAs.

## Release gate

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m evidence.validate > runtime/validation.json
python -m evidence.regression --report runtime/validation.json
```

Regression checks source hashes, each scale probe's independent source/KPI totals, original sample totals and quality-check inventory. CI compares to the prior committed approved baseline, not merely a new report. A difference means review the change, validate intended metric/contract changes with the business owner and record approval (including a versioned contract/baseline migration); never edit the baseline solely to make failed tests green. The provided gate deliberately blocks any previous-baseline difference; a future explicitly approved contract change needs a reviewed CI policy/migration update.

Browser suite: install `requirements-browser.txt` then `python -m playwright install chromium`, run a fresh 5,000-row demo server, and run `python tests/browser_smoke.py`. Docker and browser workflows produce evidence in CI when available.
