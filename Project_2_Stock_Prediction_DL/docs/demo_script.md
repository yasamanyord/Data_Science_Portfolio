# Five-minute interview demo

**Opening (30 seconds):** "This began as my bachelor's thesis comparing RNN, GRU, MLP and LSTM on stock prices. I upgraded it into reproducible ML engineering software. I identified a preprocessing leakage risk and redesigned evaluation to protect chronological holdouts. The public demo uses fictional data."

**1. Run the application (1 minute):** Start it locally using README. Show the selected model, holdout forecast chart, persistence baseline, uncertainty interval and the clearly historical data source. Switch the chart to last 30 observations; inspect the comparison table and release gate.

**2. Explain the architecture (1 minute):** Use the Mermaid chart. Show how the pipeline validates a CSV, transforms lagged returns, selects via expanding validation, refits and evaluates once, writes checksummed artifacts, and refuses failed model releases. Show GET /api/report and model.json.

**3. Prove change safety (1 minute):** Execute the tests and reproduction regression command. Explain the negative control that alters holdout prices without changing fitted coefficients and the degraded-candidate gate. Highlight that the neural architectures are available optionally, while the measured default winner is a regularized linear model. Explain why that is better than inventing a neural improvement.

**4. Explain operations (1 minute):** Show the monitor CLI, Docker config, CI and runbook. Describe an incident: adjusted historical data is revised; the old prefix no longer matches, so prediction stops until a newly reviewed experiment. Explain rollback.

**5. Scope the next step (30 seconds):** "I would start with an authorized data snapshot and client success criteria, run preregistered independent periods, measure calibration and baseline performance, and run in shadow mode before any company adoption. I would not position a synthetic example as real financial predictive performance."

## Questions to practice

- Why was MinMax scaling before chronological splitting a leakage risk?
- Why predict returns instead of raw price levels?
- What can walk-forward validation tell us that random splits cannot?
- Why does persistence matter; why is direction match not a trading return?
- How do you know a model change didn't make things worse?
- What does uncertainty coverage under 90% mean?
- How do you detect revised data and monitor performance after release?
- What is not yet live tested? TensorFlow, actual provider, public deployment and independent real data.
