"""Validated daily observations and strictly causal feature engineering."""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

MAX_ROWS = 50_000


@dataclass(frozen=True)
class Series:
    dates: tuple[str, ...]
    close: np.ndarray
    ticker: str
    source: str
    fingerprint: str


def parse_csv(text: str, ticker: str, source: str) -> Series:
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 15 or not all(c.isalnum() or c in ".-^" for c in ticker):
        raise ValueError("Invalid ticker identifier")
    if not source.strip() or len(source) > 200:
        raise ValueError("A short data source description is required")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["date", "close"]:
        raise ValueError("CSV must have exactly the header date,close")
    dates, prices = [], []
    last = None
    for i, row in enumerate(reader, 2):
        if i > MAX_ROWS + 1:
            raise ValueError("Too many observations")
        try:
            if None in row:
                raise ValueError("Unexpected extra field")
            day = date.fromisoformat(row["date"])
            if day.isoformat() != row["date"]:
                raise ValueError("Use YYYY-MM-DD")
            if not source.startswith("synthetic:") and day > date.today():
                raise ValueError("Future observation")
            price = float(row["close"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Invalid observation at CSV row {i}") from exc
        if not np.isfinite(price) or not 1e-6 <= price <= 1e9:
            raise ValueError(f"Non-finite or invalid price at row {i}")
        if last is not None and day <= last:
            raise ValueError("Dates must be strictly increasing and unique")
        dates.append(day.isoformat())
        prices.append(price)
        last = day
    if len(prices) < 2:
        raise ValueError("At least two observations required")
    canonical = csv_text(dates, prices)
    return Series(tuple(dates), np.asarray(prices, dtype=float), ticker, source,
                  hashlib.sha256(canonical.encode()).hexdigest())


def csv_text(dates, prices) -> str:
    return "date,close\n" + "".join(f"{d},{float(p):.17g}\n" for d, p in zip(dates, prices))


def load_csv(path: Path, ticker: str, source: str) -> Series:
    if path.stat().st_size > 4_000_000:
        raise ValueError("CSV exceeds size limit")
    return parse_csv(path.read_text(encoding="utf-8-sig"), ticker, source)


def synthetic(seed: int = 42, rows: int = 900) -> Series:
    """Fictional business-day observations; never real AAPL or a market feed."""
    if not 300 <= rows <= MAX_ROWS:
        raise ValueError("Synthetic dataset must contain 300–50000 rows")
    rng = np.random.default_rng(seed)
    dates, current = [], date(2020, 1, 1)
    while len(dates) < rows:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    returns = np.zeros(rows)
    for i in range(1, rows):
        # Two fictional volatility regimes; predictable structure for smoke-testing.
        sigma = .009 if i < int(rows * .7) else .014
        returns[i] = .0003 + .36 * returns[i-1] + sigma * rng.normal()
    return parse_csv(csv_text(dates, np.round(100 * np.exp(np.cumsum(returns)), 8)), "DEMO",
                     f"synthetic:seed={seed};rows={rows}")


def features(close: np.ndarray, feature_set: str) -> np.ndarray:
    """Row i only uses prices <= i. No backfill or centered windows."""
    if feature_set not in {"returns", "technical"}:
        raise ValueError("Unknown feature set")
    log_price = np.log(close)
    ret = np.r_[0., np.diff(log_price)]
    if feature_set == "returns":
        return ret[:, None]
    result = np.full((len(close), 5), np.nan)
    for i in range(20, len(close)):
        window = ret[i-19:i+1]
        gain = np.maximum(window, 0).mean()
        loss = np.maximum(-window, 0).mean()
        rsi = gain / (gain + loss) if gain + loss else .5
        result[i] = [ret[i], log_price[i]-log_price[i-4:i+1].mean(),
                     log_price[i]-log_price[i-19:i+1].mean(), window.std(), rsi-.5]
    return result


def windows(series: Series, lookback: int, feature_set: str):
    if not 5 <= lookback <= 180:
        raise ValueError("Lookback must be 5–180")
    feats = features(series.close, feature_set)
    start = lookback + (20 if feature_set == "technical" else 1)
    if len(feats) <= start:
        raise ValueError("Insufficient observations for a complete window")
    idx = np.arange(start, len(feats))
    X = np.stack([feats[i-lookback:i] for i in idx])
    y = np.log(series.close[idx] / series.close[idx-1])
    return X, y, idx


def latest_window(series: Series, lookback: int, feature_set: str):
    required = lookback + (20 if feature_set == "technical" else 1)
    if len(series.close) < required:
        raise ValueError(f"Need at least {required} observations")
    return features(series.close, feature_set)[-lookback:][None, :, :]

def demo_series(seed=42, rows=900):
    """Use the committed frozen fixture for cross-platform regression, generate variants otherwise."""
    fixture = Path(__file__).resolve().parents[1]/"artifacts"/"demo"/"observations.csv"
    if seed == 42 and rows == 900 and fixture.exists():
        return load_csv(fixture, "DEMO", "synthetic:seed=42;rows=900")
    return synthetic(seed, rows)
