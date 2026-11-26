# Architecture and validation design

## Requirements and ownership

The product is a research and engineering workspace: an analyst loads one ticker snapshot, runs an experiment, inspects the results, and either accepts or rejects an evaluated model. A hiring reviewer can run a completely fictional demonstration without keys. Nothing executes trades, recommends purchases, or queries brokerage customer data.

| Component | Responsibility |
|---|---|
| data.py / fetch.py | Strict schema, provider normalization, canonical input fingerprint, causal features |
| models.py | Persistence, ridge with intercept and two preset strengths; optional Keras builders |
| evaluate.py | Temporal partition, expanding folds, aligned metrics, interval radius, gate |
| pipeline.py | Fixed candidate selection, pre-holdout refit, test evaluation and bundle output |
| artifact.py | Bundle and input prefix integrity checks, fail-closed inference |
| cli.py | Training, reproducibility comparison and local inference |
| monitor.py | Frozen-model shadow evaluation on newly observed sessions |
| api.py / static | Read-only fictional dashboard, JSON contracts, security headers and logging |

## Avoiding data leakage

1. Parse ordered, unique dates, positive finite prices, and a source label. Input is one ticker; all market sessions must be completed. Adjusted-close consistency is provider responsibility.
2. Compute causal returns and optional features (MA deviations over 5/20 observations, trailing 20-return volatility and simple normalized RSI). No centered window or backfill. First technical row is valid after 20 actual returns.
3. For target index t, feature window ends at t−1; target is log(close[t]/close[t−1]). Past context may cross a partition boundary; target labels never do.
4. Reserve last 20% of valid targets for holdout. Divide preceding targets into initial 60% training and three disjoint expanding-window validation blocks totaling 20%. Each fold fits training-only scaler and estimators. Neural early stopping uses a chronological inner split, not outer validation.
5. Select the lowest validation price MAE among predeclared candidates (persistence, two ridge penalties, optionally all five networks). Refit selected configuration on pre-holdout targets. Freeze it before testing. For neural models, the inner early-stopping slice is still withheld from fitting.
6. Test predictions are rolling-origin one-step forecasts from actual previously observed prices, not recursive multiple steps. Convert return forecasts to positive prices; nonfinite or extreme returns fail closed.
7. Compare to last known close persistence for exactly the same holdout dates. The holdout gate allows no more than 2% error degradation on RMSE, MAE, and return MAE; it never changes the selected configuration. No automatic switching after test failure.
8. Estimate a nominal 90% residual radius on widening validation folds, then apply it in log-return space. Report empirical coverage on test. Model selection and calibration share validation data; market returns are dependent and nonstationary. The interval is not a formal guarantee.

The gate is intentionally simple and strict enough to teach model release governance. It is not proof of profitability, statistical significance, or calibration. An independent, untouched later time period and more tickers are needed before real-world acceptance. Repeated tuning on the same public fixture means it is a regression suite, not a research holdout.

## Model comparison

Study the effect of `--lookback 60` vs `90`, `--features returns` vs `technical` and `--deep`. Run each with a separate directory; compare rolling validation results, not test outcomes, to decide the configuration. Because feature warm-up and lookbacks can change target ranges, do not compare different holdout dates as if paired. For a formal ablation, reserve identical evaluation dates across all configurations in an external preregistered procedure.

## Metrics

- RMSE: larger errors penalized quadratically.
- MAE: typical absolute price error.
- MAPE: absolute percentage error against actual positive prices.
- Direction sign match: includes unchanged class, so persistence has 0% for continuously changing prices.
- Return MAE: absolute difference of log returns multiplied by 100.
- Interval coverage and average width: assess uncertainty, not a promise.
- Early/late holdout subgroup metrics help flag changing regimes; one split is not enough to measure drift comprehensively.

## Test strategy

Automated unit and integration tests check parsing, missing/invalid values, duplicate dates, causal features, target alignment, scaling, folds, model arithmetic, metrics, promotion logic, artifact tampering, ticker and history mismatch, failed approval, report comparability, monitoring and read-only API behavior. One negative control changes the entire holdout and confirms the validation scores and fitted coefficients stay unchanged. Another degrades a report and confirms the regression gate fails. Provider tests cover single and multi-index fixtures; no external API called. Optional TensorFlow tests train all architectures and run a small end-to-end comparison. Browser test verifies chart changes and narrow viewport overflow using Playwright. Verify CI status independently.

## Tradeoffs and future work

NumPy/JSON weights are small, deterministic and easy to inspect, avoiding unsafe pickle loading. Keras uses safe-mode loading for locally trusted artifacts. SHA-256 is integrity, not authenticity; malicious actors who can rewrite files can recompute hashes. For production, use signed artifacts, a controlled model registry, separate release approval, data access policy and independent evaluation. The data schema intentionally uses close-only observations; add normalized volume or OHLC with leakage tests and a schema/version migration if a client requires it.

Original thesis files are preserved; the original scaler trained on the full series and the historic other_Models file includes prose mixed with code. The new pipeline replaces both in the operational path. The old README's numbers referenced an absent run_experiments.py, so those historical metrics are not treated as validated.
