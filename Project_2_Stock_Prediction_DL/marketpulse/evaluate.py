"""Time-ordered validation, metrics, empirical bands and release checks."""
from __future__ import annotations

import numpy as np


def split_indices(n):
    a, b = int(n * .6), int(n * .8)
    if min(a, b-a, n-b) < 30:
        raise ValueError("Need >=30 windows in every chronological partition")
    return a, b


def folds(n, count=3):
    """Expanding train / nonoverlapping validation blocks within first 80%."""
    a, b = split_indices(n)
    edges = np.linspace(a, b, count+1, dtype=int)
    return [(slice(0, int(left)), slice(int(left), int(right)))
            for left, right in zip(edges[:-1], edges[1:])]


def prices(previous, returns):
    returns = np.asarray(returns, dtype=float)
    if not np.all(np.isfinite(returns)) or np.any(np.abs(returns) > 2):
        raise ValueError("Invalid forecast return; refusing extreme/nonfinite output")
    return previous * np.exp(returns)


def metrics(actual, pred, previous):
    actual, pred, previous = map(lambda x: np.asarray(x, dtype=float), (actual, pred, previous))
    if actual.shape != pred.shape or actual.shape != previous.shape or not len(actual):
        raise ValueError("Metric arrays must be aligned and nonempty")
    if not all(np.all(np.isfinite(x)) for x in (actual, pred, previous)):
        raise ValueError("Invalid metric values")
    error = pred-actual
    return {
        "n": int(len(actual)), "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "mape_pct": float(np.mean(np.abs(error / actual))*100),
        "directional_accuracy_pct": float(np.mean(np.sign(pred-previous) == np.sign(actual-previous))*100),
        "return_mae_pct": float(np.mean(np.abs(np.log(pred/previous)-np.log(actual/previous)))*100),
    }


def calibrated_radius(y, pred, coverage=.9):
    residual = np.sort(np.abs(np.asarray(y)-np.asarray(pred)))
    rank = min(len(residual), int(np.ceil((len(residual)+1)*coverage)))
    return float(residual[rank-1])


def release_gate(candidate, baseline, tolerance=.02):
    if not 0 <= tolerance <= .1:
        raise ValueError("Invalid release tolerance")
    checks = {metric: bool(candidate[metric] <= baseline[metric]*(1+tolerance)+1e-12)
              for metric in ("rmse", "mae", "return_mae_pct")}
    return {"passed": all(checks.values()), "checks": checks,
            "tolerance": tolerance, "policy": "candidate <= persistence * (1 + tolerance)"}
