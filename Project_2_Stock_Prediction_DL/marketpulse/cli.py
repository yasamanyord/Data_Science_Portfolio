"""Command-line workflow for research, comparison and inference."""
import argparse
import json
from pathlib import Path

from .artifact import forecast, read_bundle
from .data import csv_text, demo_series, load_csv
from .pipeline import run


def compare(reference, candidate, tolerance=.02):
    """Same-data regression check; not a replacement for independent holdout."""
    for key in ("dataset", "split", "counts"):
        if reference[key] != candidate[key]:
            raise ValueError(f"Incomparable reports: {key}")
    for key in ("lookback", "feature_set"):
        if reference["config"][key] != candidate["config"][key]:
            raise ValueError(f"Incomparable reports: {key}")
    if len(reference["holdout"]) != len(candidate["holdout"]) or any(
        (a["date"], a["actual"], a["persistence"]) != (b["date"], b["actual"], b["persistence"])
        for a, b in zip(reference["holdout"], candidate["holdout"])
    ):
        raise ValueError("Incomparable holdout labels")
    checks = {m: candidate["test"]["candidate"][m] <= reference["test"]["candidate"][m]*(1+tolerance)+1e-10
              for m in ("rmse", "mae", "return_mae_pct")}
    checks["candidate_gate_passed"] = candidate["gate"]["passed"] is True
    return {"passed": all(checks.values()), "checks": checks, "tolerance": tolerance}


def parser():
    p = argparse.ArgumentParser(prog="marketpulse", description="One-session forecasting research; not trading advice")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("demo", "train"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--output", required=True, type=Path)
        cmd.add_argument("--lookback", type=int, default=60)
        cmd.add_argument("--features", choices=["returns", "technical"], default="returns")
        cmd.add_argument("--seed", type=int, default=42)
        cmd.add_argument("--deep", action="store_true", help="Install requirements-deep.txt first")
        cmd.add_argument("--epochs", type=int, default=20)
        if name == "demo":
            cmd.add_argument("--rows", type=int, default=900)
        else:
            cmd.add_argument("--csv", type=Path, required=True)
            cmd.add_argument("--ticker", required=True)
            cmd.add_argument("--source", required=True)
    pred = sub.add_parser("predict")
    pred.add_argument("--artifact", type=Path, required=True)
    pred.add_argument("--csv", type=Path, required=True)
    pred.add_argument("--ticker", required=True)
    pred.add_argument("--source", required=True)
    cmp = sub.add_parser("compare")
    cmp.add_argument("--reference", type=Path, required=True)
    cmp.add_argument("--candidate", type=Path, required=True)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command in {"demo", "train"}:
            series = demo_series(args.seed, args.rows) if args.command == "demo" else load_csv(args.csv, args.ticker, args.source)
            if args.command == "train" and series.source.startswith("synthetic:"):
                raise ValueError("Use the demo command for synthetic runs")
            report = run(series, args.output, args.lookback, args.features, args.deep, args.seed, args.epochs)
            if args.command == "demo":
                (args.output/"observations.csv").write_text(csv_text(series.dates, series.close), encoding="utf-8")
            print(json.dumps({"selected_model": report["selected_model"], "gate": report["gate"],
                              "holdout": report["test"], "artifact": str(args.output)}, indent=2))
            return 0 if report["gate"]["passed"] else 2
        if args.command == "predict":
            print(json.dumps(forecast(args.artifact, load_csv(args.csv, args.ticker, args.source)), indent=2))
            return 0
        result = compare(read_bundle(args.reference)[1], read_bundle(args.candidate)[1])
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 2
    except (OSError, ValueError, ImportError, KeyError) as exc:
        p.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
