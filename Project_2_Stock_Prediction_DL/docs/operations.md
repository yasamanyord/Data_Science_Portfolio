# Deployment and operational runbook

## Local setup
Install Python 3.11/3.12 and core requirements. Start Uvicorn on loopback. GET /health must report healthy synthetic service; GET /api/forecast must have synthetic=true and the evaluated as-of date, or HTTP 409 on gate rejection. Open / and /openapi.json. See README for Windows and Linux/macOS instructions.

Docker build from this project directory: docker compose up --build. Default mapped host port is loopback 8000. Docker is non-root and read-only at runtime; TLS, rate limiting, platform networking and logs are host responsibilities. Configuration was not executed locally; the initial GitHub Actions Docker smoke job passed. Check later workflow results before deploying.

### Public demonstration
If publishing, configure a container service with this folder as root/build context, Dockerfile, HTTP port 8000, health /health and TLS. Use only the bundled fictional artifact. No secrets or live data are necessary. A successful build and health response are deployment checks, not proof of production suitability.

## Release procedure
1. Create a new experiment directory. Never overwrite the approved reference. Record dataset and split fingerprint, feature schema, seed, environment, model, held-out performance and release decision.
2. Run unit/integration tests and CI. Reproduce the default fixture: python -m marketpulse demo --output runs/reproduction
3. Run python -m marketpulse compare --reference artifacts/demo --candidate runs/reproduction. It requires the exact same dataset, dates, actual labels, feature/window configuration; blocks a >2% candidate regression on any monitored metric or a rejected candidate. Negative controls prove the gate fails when evidence degrades.
4. For a new real-data snapshot, run the chronological evaluation, review the gate and independently authored acceptance criteria. Review new model performance against previously approved models on common dates. Avoid using test labels to adjust hyperparameters.
5. Promote only a reviewed bundle. Keep prior deployment version and image digest; rollback by restarting previous verified image or pointing local CLI to prior artifact. Verify health and report checksum. Do not overwrite historic artifacts.

## Forecast and monitoring
Use the local CLI with same ticker, same source and the exact evaluated history prefix; append completed new sessions. The model is frozen, not automatically retrained. If a historical adjustment alters the prefix, stop and create a fresh experiment. Use python -m marketpulse.monitor against the extended CSV. It evaluates at most 90 new realized observations, each predicted from prior history only. Review alerts for fewer than 20 observations, degradation vs persistence or coverage <80%. These thresholds are illustrative and not validated on real markets.

Investigate drift: inspect latest realized error and interval coverage, compare historical and recent MAE, inspect price adjustment/corporate events, confirm data freshness/calendar. Do not retrain automatically or issue forecasts to end users on an alert without review.

HTTP middleware logs route, status and latency; run Uvicorn with --no-access-log if minimizing URL/query logging. Use a host to aggregate logs, set latency/error SLOs, rate-limit and alert. No metric exporter, alerting service, authenticated real-data endpoint, scheduler or persistent customer storage is claimed. Development environment/API smoke tests are not load or security penetration tests.

## Failure handling
| Incident | Action |
|---|---|
| Data fetch fails/empty | Preserve previous snapshot, record provider error, retry authorized acquisition; don't fabricate observations |
| Duplicate/nonfinite values | Reject file and correct at source; no backfill using future observations |
| Candidate gate fails | Retain report; no inference approval; review methodology and new validation data |
| Integrity/ticker/prefix mismatch | Stop, restore verified bundle or rerun experiment after review |
| Monitoring alerts | Pause real-world use, investigate regime/data changes and model quality |
| Service fails health | Roll back previous image/artifact, inspect startup logs, run smoke checks |

## Before company use
- Define the actual workflow and what decisions are explicitly out of scope; risk owner signs off.
- Use licensed/authorized data, data quality controls, exchange calendar, point-in-time corporate actions and private storage.
- Establish preregistered independent forward-time evaluation, appropriate baselines, calibration checks and meaningful acceptance criteria; document failure modes.
- Control artifact signing, release registry, secret storage, authN/authZ, TLS, network egress, dependency scans, backups, incident response, SLOs and load testing.
- Operate in research/shadow mode with a human reviewer. Do not connect to live execution systems.
