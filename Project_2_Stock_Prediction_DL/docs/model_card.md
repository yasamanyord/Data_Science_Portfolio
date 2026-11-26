# Model card — MarketPulse ML 2.0

**Owner:** Yasaman Yord. **Task:** one-observation-ahead closing-price research. **Default release:** regularized ridge (alpha 500), trained on standardized 60-observation log-return windows. **Inputs:** validated date and adjusted close; ticker/provenance bound to model. **Output:** point price, empirical lower/upper bound, as-of date and gate approval.

## Intended use
- Education, time-series experimentation, reproducibility, ML engineering interview demonstration.
- Internal research on authorized historical data under human supervision.
- Not an autonomous trader, advisory system, portfolio optimizer, real-time quote service or regulatory/compliance tool.

## Data and performance
The 900-observation default fixture is intentionally fictional with two volatility regimes and autocorrelation; it is suitable for verifying pipeline behavior, not proving accuracy on securities. The frozen artifact, manifest and raw report contain dates, fingerprint, metrics, model choice and configuration. The reported final 168-target holdout achieved RMSE 1.3621 vs persistence 1.4491 and empirical 90% interval coverage 86.90%. It under-covered nominal coverage. The optional neural networks are implemented but not locally trained/verified due to missing TensorFlow.

## Failure cases
Market shocks, splits and dividends, revised adjusted histories, gaps, missing exchange sessions, regime shifts, unusually high volatility, low-liquidity securities and unseen tickers can invalidate results. The model does not know market calendars, corporate news, transaction costs, bid/ask spreads or latency. A good price RMSE may not imply usable directional signal. No price forecast guarantees or real trading backtest claims are made.

## Risk controls
No live trading integration. No credentials or private data in public demo. Strict input validation; bundle checksum, provenance and evaluated-prefix checks; reject nonfinite/extreme forecasts; block failed-release models; display measured uncertainty and historical timestamp. Model artifacts must originate from a trusted path; checksums do not prove authenticity. No customer or personally identifiable data is needed.

## Release acceptance
For real client research, define evaluation windows and outcomes before training; compare multiple independent periods and tickers against stronger benchmarks, inspect uncertainty coverage and regime failures; review authorized source usage and versioned data; sign off deployment security, monitoring, rollback and human ownership. Do not reuse the synthetic metric as a production KPI.
