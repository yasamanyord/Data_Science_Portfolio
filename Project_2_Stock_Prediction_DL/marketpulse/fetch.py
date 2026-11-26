"""Optional Yahoo Finance acquisition; separate from reproducible offline training."""
import argparse
from datetime import date
from pathlib import Path

from .data import csv_text, parse_csv

SOURCE = "Yahoo Finance adjusted close via yfinance"


def normalize(frame, ticker):
    """Handle single-level and one-symbol MultiIndex Close columns."""
    if frame.empty:
        raise ValueError("Provider returned no observations")
    closes = frame["Close"]
    if getattr(closes, "ndim", 0) == 2:
        if closes.shape[1] != 1:
            raise ValueError("Expected a single ticker")
        closes = closes.iloc[:, 0]
    return parse_csv(csv_text([d.date().isoformat() for d in closes.index], closes.to_numpy()),
                     ticker, SOURCE)


def main(argv=None):
    p = argparse.ArgumentParser(description="Fetch an explicit historical window; end date exclusive")
    p.add_argument("--ticker", required=True)
    p.add_argument("--start", required=True, type=date.fromisoformat)
    p.add_argument("--end", required=True, type=date.fromisoformat)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    if args.start >= args.end or args.end > date.today():
        p.error("Specify start < end <= today; end is exclusive")
    if args.output.exists():
        p.error("Refusing to overwrite an existing snapshot")
    try:
        ticker = args.ticker.strip().upper()
        # Validate before making the network request; one ticker only.
        if not ticker or len(ticker)>15 or not all(c.isalnum() or c in ".-^" for c in ticker):
            raise ValueError("Invalid ticker")
        import yfinance as yf
        frame = yf.download(ticker, start=args.start.isoformat(), end=args.end.isoformat(),
                            auto_adjust=True, interval="1d", progress=False,
                            threads=False, timeout=20)
        series = normalize(frame,ticker)
        if series.dates[0] < args.start.isoformat() or series.dates[-1] >= args.end.isoformat():
            raise ValueError("Provider returned dates outside requested range")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            f.write(csv_text(series.dates,series.close))
        print(f"{series.ticker}: {len(series.close)} observations; sha256={series.fingerprint}")
        print(f"Use --source \"{SOURCE}\" for training.")
    except (ImportError,OSError,ValueError,KeyError) as exc:
        p.exit(1,f"Acquisition failed: {exc}\n")


if __name__ == "__main__":
    main()
