"""Repeatable release evidence: independent source totals + replay + rollback + recovery."""
import csv
from hashlib import sha256
import json
from pathlib import Path
import platform
import sqlite3
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

# Support python -m evidence.validate from project root.
from warehouse.analytics import report, export_monthly
from warehouse.contract import ContractError
from warehouse.db import init, ingest
from warehouse.generate import generate
from warehouse.legacy import export_legacy
from warehouse.quality import evaluate, backup


def source_totals(filename):
    with filename.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    return {
        "sales": len(rows), "units": sum(int(r["quantity"]) for r in rows),
        "gross_cents": sum(int(r["gross_cents"]) for r in rows),
        "discount_cents": sum(int(r["discount_cents"]) for r in rows),
        "net_cents": sum(int(r["gross_cents"]) - int(r["discount_cents"]) for r in rows),
        "customers": len({r["customer_id"] for r in rows}),
        "products": len({r["product_id"] for r in rows}),
    }


def validate():
    output = {"environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                                "platform": platform.system(), "architecture": platform.machine()},
              "notes": "Synthetic, seed 42; timings are single-run local measurements, not a production SLA.",
              "scenarios": []}
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for count in (5000, 50000):
            source = generate(root / f"{count}.csv", count, 42)
            database = root/f"{count}.sqlite3"
            init(database)
            t = perf_counter()
            run = ingest(database, source)
            load_duration = perf_counter() - t
            t = perf_counter()
            analytics = report(database)
            query_duration = perf_counter() - t
            expected = source_totals(source)
            actual = {key: analytics["summary"][key] for key in expected}
            assert actual == expected
            quality = evaluate(database)
            assert quality["passed"] and run["rows_inserted"] == count
            replay = ingest(database, source)
            assert replay["status"] == "replayed" and replay["rows_inserted"] == 0
            assert report(database)["summary"] == analytics["summary"]
            scenario = {
                "rows": count, "file_sha256": sha256(source.read_bytes()).hexdigest(),
                "independent_source_totals": expected,
                "warehouse_totals": actual, "quality": quality,
                "replay": {"status": replay["status"], "rows_inserted": replay["rows_inserted"],
                           "rows_skipped": replay["rows_skipped"]},
                "timings_seconds": {"load": round(load_duration, 4), "full_analytics": round(query_duration, 4)},
            }
            if count == 5000:
                invalid = root/"bad.csv"
                with source.open(newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    row = next(reader)
                    clean = dict(row, sale_id="VALID-BUT-ROLLBACK")
                    broken = dict(row, sale_id="BAD", quantity="0")
                with invalid.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(row))
                    writer.writeheader()
                    writer.writerows([clean, broken])
                try:
                    ingest(database, invalid)
                    raise AssertionError("invalid batch accepted")
                except ContractError as exc:
                    assert "INVALID_QUANTITY" in str(exc)
                assert report(database)["summary"] == analytics["summary"]
                scenario["negative_control"] = {"invalid_batch_rejected": True, "totals_unchanged": True}
                saved = root/"backup.sqlite3"
                assert backup(database,saved)["passed"]
                assert report(saved)["summary"] == analytics["summary"]
                scenario["backup_verified"] = True
                scenario["months_exported"] = export_monthly(database,root/"monthly.csv")
            output["scenarios"].append(scenario)
        old = root/"legacy.csv"
        export_legacy(old, assume_income_is_gross=True, currency="USD")
        legacy_db = root/"legacy.sqlite3"
        init(legacy_db)
        ingest(legacy_db,old)
        expected = source_totals(old)
        actual = {key:report(legacy_db)["summary"][key] for key in expected}
        assert expected==actual and evaluate(legacy_db)["passed"]
        output["legacy_demo"] = {"assumptions": "Income treated as gross USD, original currency/meaning unspecified",
                                 "totals": actual, "quality_passed": True}
    output["passed"] = True
    return output


if __name__=="__main__":
    print(json.dumps(validate(),indent=2))
