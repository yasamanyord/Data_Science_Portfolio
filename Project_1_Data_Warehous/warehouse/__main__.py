"""Run from the project directory: python -m warehouse --help."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from tempfile import TemporaryDirectory

from .analytics import export_monthly, report, runs
from .contract import ContractError
from .db import DEFAULT_DB, init, ingest
from .generate import generate
from .legacy import export_legacy
from .quality import backup, evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Dedicated SQLite database")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    gen = sub.add_parser("generate")
    gen.add_argument("csv", type=Path)
    gen.add_argument("--rows", type=int, default=5000)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--start-id", type=int, default=1)
    legacy = sub.add_parser("legacy-export")
    legacy.add_argument("csv", type=Path)
    legacy.add_argument("--assume-income-is-gross", action="store_true")
    legacy.add_argument("--currency", choices=["USD"])
    load = sub.add_parser("ingest")
    load.add_argument("csv", type=Path)
    pipeline = sub.add_parser("pipeline", help="Ingest and run the quality release gate")
    pipeline.add_argument("csv", type=Path)
    sub.add_parser("check")
    sub.add_parser("report")
    sub.add_parser("runs")
    export = sub.add_parser("export")
    export.add_argument("csv", type=Path)
    save = sub.add_parser("backup")
    save.add_argument("destination", type=Path)
    demo = sub.add_parser("demo")
    demo.add_argument("--rows", type=int, default=5000)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init(args.db)
            result = {"initialized": True}
        elif args.command == "generate":
            result = {"csv": str(generate(args.csv, args.rows, args.seed, args.start_id))}
        elif args.command == "legacy-export":
            result = {"rows_exported": export_legacy(args.csv, assume_income_is_gross=args.assume_income_is_gross,
                                                      currency=args.currency)}
        elif args.command == "ingest":
            result = ingest(args.db, args.csv)
        elif args.command == "pipeline":
            result = {"load": ingest(args.db, args.csv), "quality": evaluate(args.db)}
        elif args.command == "check":
            result = evaluate(args.db)
        elif args.command == "report":
            result = report(args.db)
        elif args.command == "runs":
            result = runs(args.db)
        elif args.command == "export":
            result = {"months_exported": export_monthly(args.db, args.csv)}
        elif args.command == "backup":
            result = backup(args.db, args.destination)
        elif args.command == "demo":
            init(args.db)
            with TemporaryDirectory() as tmp:
                csv = Path(tmp) / "synthetic_demo.csv"
                generate(csv, args.rows)
                result = {"load": ingest(args.db, csv), "quality": evaluate(args.db)}
        print(json.dumps(result, indent=2))
        if isinstance(result, dict) and (result.get("passed") is False or result.get("quality", {}).get("passed") is False):
            return 1
        return 0
    except sqlite3.Error:
        print("ERROR: database operation failed (check path, permissions and schema)", file=sys.stderr)
        return 1
    except (ContractError, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
