"""Block silent metric/data-contract regressions against an approved baseline."""
import argparse
import json
from pathlib import Path
from .validate import validate


def project(report):
    return {"schema_version": 1, "seed": 42,
            "scenarios": [{"rows": s["rows"], "file_sha256": s["file_sha256"],
                           "warehouse_totals": s["warehouse_totals"],
                           "quality_checks": [c["name"] for c in s["quality"]["checks"]]}
                          for s in report["scenarios"]],
            "legacy_totals": report["legacy_demo"]["totals"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=Path(__file__).with_name("baseline.json"))
    parser.add_argument("--report", type=Path, default=None, help="Optional existing validation report")
    args = parser.parse_args()
    prior = json.loads(args.baseline.read_text())
    current = json.loads(args.report.read_text()) if args.report else validate()
    def failed():
        raise SystemExit("FAIL: baseline differs or quality check failed. Review contract and metric changes; never silently rebaseline.")
    if not current.get("passed") or any(not s["quality"]["passed"] for s in current["scenarios"]):
        failed()
    if prior != project(current):
        failed()
    print("PASS: source file hashes, KPI totals, quality check inventory and original sample totals match the approved baseline.")


if __name__ == "__main__":
    main()
