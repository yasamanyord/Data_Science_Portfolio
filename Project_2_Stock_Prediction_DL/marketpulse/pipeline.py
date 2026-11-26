"""One-command experiment, versioned evidence, and explicit model promotion."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from . import __version__
from .data import Series, latest_window, windows
from .evaluate import calibrated_radius, folds, metrics, prices, release_gate, split_indices
from .models import NEURAL, RIDGE, fit_neural, fit_ridge, fit_scaler, neural_predict, ridge_predict, scale


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def fit(name, X, y, seed, epochs):
    if name == "persistence":
        return None, np.zeros(X.shape[-1]), np.ones(X.shape[-1])
    # For neural models even the inner stopping slice is excluded from scaler fitting.
    scaler_fit = X[:int(len(X)*.85)] if name in NEURAL else X
    center, spread = fit_scaler(scaler_fit)
    Z = scale(X, center, spread)
    estimator = fit_ridge(Z, y, RIDGE[name]) if name in RIDGE else fit_neural(name, Z, y, seed, epochs)
    return estimator, center, spread


def predict(name, fitted, X):
    estimator, center, spread = fitted
    if name == "persistence":
        return np.zeros(len(X))
    Z = scale(X, center, spread)
    return ridge_predict(Z, estimator) if name in RIDGE else neural_predict(estimator, Z)


def run(series: Series, output: Path, lookback=60, feature_set="returns",
        deep=False, seed=42, epochs=20):
    if not 1 <= epochs <= 200:
        raise ValueError("Epochs must be 1–200")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be new or empty; do not overwrite evidence")
    X, y, idx = windows(series, lookback, feature_set)
    train_end, test_start = split_indices(len(X))
    prev, actual = series.close[idx-1], series.close[idx]
    names = ["persistence", *RIDGE] + (list(NEURAL) if deep else [])
    validation = {}
    for name in names:
        predictions = []
        for tr, va in folds(len(X)):
            fitted = fit(name, X[tr], y[tr], seed, epochs)
            predictions.extend(predict(name, fitted, X[va]))
        pred = np.asarray(predictions)
        segment = slice(train_end, test_start)
        validation[name] = {"metrics": metrics(actual[segment], prices(prev[segment], pred), prev[segment]),
                            "residual_radius": calibrated_radius(y[segment], pred)}
    candidate = min(names, key=lambda name: validation[name]["metrics"]["mae"])
    # Refit the selected configuration using all pre-test windows. Holdout never selects models.
    trained = fit(candidate, X[:test_start], y[:test_start], seed, epochs)
    test_pred_ret = predict(candidate, trained, X[test_start:])
    test_prev, test_actual = prev[test_start:], actual[test_start:]
    test_pred = prices(test_prev, test_pred_ret)
    test_metrics = metrics(test_actual, test_pred, test_prev)
    baseline = metrics(test_actual, test_prev, test_prev)
    gate = release_gate(test_metrics, baseline)
    radius = validation[candidate]["residual_radius"]
    lower = prices(test_prev, test_pred_ret-radius)
    upper = prices(test_prev, test_pred_ret+radius)
    last_return = float(predict(candidate, trained, latest_window(series, lookback, feature_set))[0])
    last_price = float(series.close[-1])
    point = float(prices(last_price, last_return))
    band = [float(prices(last_price, last_return-radius)), float(prices(last_price, last_return+radius))]
    split_dates = {"first_train_target": series.dates[idx[0]],
                   "first_validation_target": series.dates[idx[train_end]],
                   "first_holdout_target": series.dates[idx[test_start]],
                   "last_holdout_target": series.dates[idx[-1]]}
    report = {
        "schema_version": 1, "project_version": __version__,
        "dataset": {"ticker": series.ticker, "source": series.source,
                    "sha256": series.fingerprint, "rows": len(series.close),
                    "first_date": series.dates[0], "last_date": series.dates[-1],
                    "synthetic": series.source.startswith("synthetic:")},
        "config": {"lookback": lookback, "feature_set": feature_set, "seed": seed,
                   "deep": deep, "epochs": epochs, "validation_folds": 3, "ridge_alphas": RIDGE},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "split": split_dates, "counts": {"initial_train": train_end,
                                        "validation": test_start-train_end, "holdout": len(X)-test_start},
        "validation": {name: result["metrics"] for name, result in validation.items()},
        "selected_model": candidate, "test": {"candidate": test_metrics, "persistence": baseline,
                            "interval_coverage_pct": float(np.mean((test_actual>=lower)&(test_actual<=upper))*100),
                            "interval_mean_width": float(np.mean(upper-lower)),
                            "first_half": metrics(test_actual[:len(test_actual)//2], test_pred[:len(test_actual)//2],
                                                  test_prev[:len(test_actual)//2]),
                            "second_half": metrics(test_actual[len(test_actual)//2:], test_pred[len(test_actual)//2:],
                                                   test_prev[len(test_actual)//2:])},
        "gate": gate,
        "forecast": {"as_of": series.dates[-1], "last_close": last_price,
                     "point": point, "lower": band[0], "upper": band[1],
                     "horizon": "next observed session", "approved": gate["passed"]},
        "limitations": ["Educational research; no trading actions or recommendations.",
                        "One-step rolling-origin forecasts use actual earlier observations.",
                        "90% nominal empirical band; calibration is not a guarantee for dependent returns.",
                        "Synthetic evidence is not evidence of real-market skill."],
        "holdout": [{"date": series.dates[i], "actual": float(a), "prediction": float(p),
                     "persistence": float(b), "lower": float(l), "upper": float(u)}
                    for i, a, p, b, l, u in zip(idx[test_start:], test_actual, test_pred, test_prev, lower, upper)]
    }
    if deep:
        import tensorflow as tf
        report["environment"]["tensorflow"] = tf.__version__
    estimator, center, spread = trained
    model = {"schema_version": 1, "name": candidate, "ticker": series.ticker,
             "source": series.source, "training_data_sha256": series.fingerprint,
             "last_training_observation": series.dates[idx[test_start-1]],
             "evaluation_as_of": series.dates[-1], "lookback": lookback,
             "feature_set": feature_set, "center": center.tolist(), "spread": spread.tolist(),
             "radius": radius, "approved": gate["passed"]}
    output.mkdir(parents=True, exist_ok=True)
    if candidate in RIDGE:
        model["weights"] = estimator.tolist()
    elif candidate in NEURAL:
        estimator.save(output / "model.keras")
        model["keras_sha256"] = hashlib.sha256((output/"model.keras").read_bytes()).hexdigest()
    dump(output/"report.json", report)
    model["report_sha256"] = hashlib.sha256((output/"report.json").read_bytes()).hexdigest()
    dump(output/"model.json", model)
    files = ["report.json", "model.json"] + (["model.keras"] if candidate in NEURAL else [])
    dump(output/"manifest.json", {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in files})
    return report
