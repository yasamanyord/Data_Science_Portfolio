"""Frozen-model shadow evaluation on new observed prices; no live automation."""
import argparse
import json
from pathlib import Path

from .artifact import forecast, read_bundle
from .data import csv_text, load_csv, parse_csv
from .evaluate import metrics, release_gate


def shadow(folder, series, max_observations=90):
    model, report=read_bundle(folder)
    if not 1 <= max_observations <= 90:
        raise ValueError("Monitoring window must be 1–90")
    cutoff=series.dates.index(model["evaluation_as_of"])
    if cutoff == len(series.dates)-1:
        raise ValueError("No newly observed sessions after the evaluation snapshot")
    predictions, actual, previous, covered = [], [], [], []
    for i in range(max(cutoff+1,len(series.close)-max_observations),len(series.close)):
        history=parse_csv(csv_text(series.dates[:i],series.close[:i]),series.ticker,series.source)
        point=forecast(folder,history)
        outcome=series.close[i]
        predictions.append(point["point"])
        actual.append(outcome)
        previous.append(series.close[i-1])
        covered.append(bool(point["lower"] <= outcome <= point["upper"]))
    observed=metrics(actual,predictions,previous)
    baseline=metrics(actual,previous,previous)
    gate=release_gate(observed,baseline)
    coverage=sum(covered)/len(covered)*100
    return {"ticker": series.ticker, "source": series.source, "as_of": series.dates[-1],
            "n": len(actual), "candidate": observed,"persistence": baseline,
            "coverage_pct":coverage, "baseline_gate":gate,
            "historical_holdout_mae":report["test"]["candidate"]["mae"],
            "alert":len(actual)<20 or not gate["passed"] or coverage<80,
            "note":"Review required for fewer than 20 observations, gate failure or coverage below 80%. No automatic retraining."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact",required=True,type=Path)
    p.add_argument("--csv",required=True,type=Path)
    p.add_argument("--ticker",required=True)
    p.add_argument("--source",required=True)
    p.add_argument("--max-observations",type=int,default=90)
    args=p.parse_args()
    try:
        print(json.dumps(shadow(args.artifact,load_csv(args.csv,args.ticker,args.source),args.max_observations),indent=2))
    except (OSError,ValueError,KeyError,ImportError) as exc:
        p.exit(1,f"Monitoring failed: {exc}\n")


if __name__ == "__main__":
    main()
