# Verified release evidence

This record refers to actual workflow executions of the project on GitHub Actions, not synthetic status badges.

## Latest code verification

- [Full passing run 45825862505](https://github.com/yasamanyord/Data_Science_Portfolio/actions/runs/45825862505), commit `fe431bb681f4ca22c86634a8aaaa8e8f5d5a2bb0`.
- tests-and-regression: **success** — 51 unit/integration/API tests; 10 warehouse checks; independent 5,000/50,000 row reconciliation; approved baseline; JS syntax.
- browser-smoke: **success** — real Chromium desktop and mobile, 8 KPI cards, 24 monthly bars, 10 quality checks, category filtering, invalid range, empty state, reset, interactive API docs, mobile layout and month-label clipping check. The actual desktop/mobile screenshots are copied into docs from the [browser evidence artifact](https://github.com/yasamanyord/Data_Science_Portfolio/actions/runs/45825862505/artifacts/15119552604).
- docker-smoke: **success** — built the image, started Compose, checked readiness, exact 5,000-row count and quality pass.

## Defect discovered and corrected

- [Initial run 45825439889](https://github.com/yasamanyord/Data_Science_Portfolio/actions/runs/45825439889): core regression and Docker jobs passed. The browser workflow exercised initial report, filters, reset and empty-state handling, but failed an overly strict locator for the OpenAPI heading (actual heading contains version/specification labels).
- Changed the assertion to locate the actual accessible heading and verify the report link. [Second run 45825605219](https://github.com/yasamanyord/Data_Science_Portfolio/actions/runs/45825605219) passed all three jobs.
- Inspected actual desktop/mobile screenshots; improved month-label readability and added an explicit check against clipping and a prominent quality-failure status. The third run above passed.

Docker and Chromium binaries were unavailable in the local development environment, and a local Chromium download was denied. Hosted CI supplied the missing actual runtime evidence. All dataset results and screenshot values are fictional portfolio data. No company deployment or production performance SLA is claimed.
