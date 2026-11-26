"""Load only trusted local artifacts; verify integrity and block rejected forecasts."""
import hashlib
import json
from pathlib import Path

import numpy as np

from .data import csv_text, latest_window
from .evaluate import prices
from .models import NEURAL, RIDGE, neural_predict, ridge_predict, scale


def read_bundle(folder: Path):
    report_bytes = (folder/"report.json").read_bytes()
    model_bytes = (folder/"model.json").read_bytes()
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if any(hashlib.sha256(data).hexdigest() != manifest.get(name) for name, data in
           (("report.json", report_bytes), ("model.json", model_bytes))):
        raise ValueError("Bundle checksum mismatch")
    model = json.loads(model_bytes)
    report = json.loads(report_bytes)
    if (hashlib.sha256(report_bytes).hexdigest() != model.get("report_sha256")
            or model.get("schema_version") != 1 or report.get("schema_version") != 1
            or model["name"] != report["selected_model"]
            or model["ticker"] != report["dataset"]["ticker"]
            or model["source"] != report["dataset"]["source"]
            or model["training_data_sha256"] != report["dataset"]["sha256"]
            or model["evaluation_as_of"] != report["dataset"]["last_date"]
            or model["approved"] != report["gate"]["passed"]
            or model["lookback"] != report["config"]["lookback"]
            or model["feature_set"] != report["config"]["feature_set"]):
        raise ValueError("Artifact metadata/integrity mismatch")
    return model, report


def forecast(folder: Path, series):
    spec, _ = read_bundle(folder)
    if spec["approved"] is not True:
        raise ValueError("Candidate failed holdout release gate; forecast blocked")
    if (series.ticker, series.source) != (spec["ticker"], spec["source"]):
        raise ValueError("Ticker or data provenance mismatch")
    if series.dates[-1] < spec["evaluation_as_of"]:
        raise ValueError("Input ends before evaluation snapshot")
    # Require the exact evaluated prefix; revised or truncated snapshots need a new experiment.
    cutoff = series.dates.index(spec["evaluation_as_of"])
    prefix = csv_text(series.dates[:cutoff+1], series.close[:cutoff+1])
    if hashlib.sha256(prefix.encode()).hexdigest() != spec["training_data_sha256"]:
        raise ValueError("Evaluated history changed or is incomplete; retrain and revalidate")
    X = latest_window(series, spec["lookback"], spec["feature_set"])
    center, spread = np.array(spec["center"]), np.array(spec["spread"])
    if (center.shape != (X.shape[-1],) or spread.shape != center.shape
            or not np.all(np.isfinite(center)) or not np.all(np.isfinite(spread)) or np.any(spread <= 0)):
        raise ValueError("Invalid feature scaler")
    X = scale(X, center, spread)
    name = spec["name"]
    if name == "persistence":
        r = 0.
    elif name in RIDGE:
        w = np.asarray(spec["weights"])
        if w.shape != (X.size+1,) or not np.all(np.isfinite(w)):
            raise ValueError("Invalid ridge coefficients")
        r = float(ridge_predict(X, w)[0])
    elif name in NEURAL:
        import tensorflow as tf
        path = folder/"model.keras"
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["keras_sha256"]:
            raise ValueError("Neural model checksum mismatch")
        r = float(neural_predict(tf.keras.models.load_model(path, safe_mode=True, compile=False), X)[0])
    else:
        raise ValueError("Unknown model architecture")
    last = float(series.close[-1])
    radius = float(spec["radius"])
    if not np.isfinite(radius) or radius < 0:
        raise ValueError("Invalid residual radius")
    return {"as_of": series.dates[-1], "last_close": last, "point": float(prices(last, r)),
            "lower": float(prices(last, r-radius)), "upper": float(prices(last, r+radius)),
            "horizon": "next observed session", "approved": True}
