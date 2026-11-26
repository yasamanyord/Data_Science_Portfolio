import csv
from datetime import date
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import unittest

from warehouse.analytics import export_monthly, report, runs
from warehouse.contract import ContractError, FIELDS
from warehouse.db import connect, ingest, init
from warehouse.generate import generate
from warehouse.legacy import export_legacy
from warehouse.quality import backup, evaluate


def row(sale_id="S1", **changes):
    data = dict(zip(FIELDS, [sale_id, "2024-05-01", "P1", "Sofa", "Living Room", "Fabric",
                             "C1", "Toronto", "Central", "Ontario", "Canada",
                             2, 10000, 500, "USD"]))
    data.update(changes)
    return data


class WarehouseTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "warehouse.sqlite3"
        init(self.db)

    def write(self, name, *records, fields=FIELDS):
        path = self.root / name
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(records)
        return path

    def load(self, *records, name="source.csv"):
        return ingest(self.db, self.write(name, *records))

    def reject(self, records, code):
        with self.assertRaisesRegex(ContractError, code):
            self.load(*records)
        self.assertEqual(report(self.db)["summary"]["sales"], 0)
        self.assertEqual(runs(self.db)[0]["status"], "rejected")
        self.assertEqual(runs(self.db)[0]["rows_inserted"], 0)

    def test_init_idempotent(self):
        init(self.db)
        self.assertTrue(evaluate(self.db)["passed"])

    def test_refuses_existing_unrelated_db(self):
        other = self.root / "other.db"
        with sqlite3.connect(other) as db:
            db.execute("CREATE TABLE unrelated(id)")
        with self.assertRaisesRegex(RuntimeError, "dedicated"):
            init(other)

    def test_refuses_future_version(self):
        with connect(self.db) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            init(self.db)

    def test_golden_kpis_and_yoy(self):
        self.load(row(), row("S2", sold_on="2025-05-01", gross_cents=20000, discount_cents=1000),
                  row("S3", sold_on="2025-05-20", product_id="P2", product_type="Bed",
                      category="Bedroom", customer_id="C2", quantity=3, gross_cents=10000, discount_cents=0))
        result = report(self.db)
        s = result["summary"]
        self.assertEqual((s["sales"], s["units"], s["gross_cents"], s["discount_cents"],
                          s["net_cents"], s["customers"], s["repeat_customers"]),
                         (3, 7, 40000, 1500, 38500, 2, 1))
        self.assertEqual(s["discount_pct"], 3.75)
        self.assertEqual(result["monthly"][0]["yoy_pct"], None)
        self.assertEqual(result["monthly"][1]["prior_year_net_cents"], 9500)
        self.assertAlmostEqual(result["monthly"][1]["yoy_pct"], 205.26)
        self.assertEqual(result["products"][0]["product_type"], "Sofa")
        self.assertTrue(evaluate(self.db)["passed"])

    def test_filters_inclusive(self):
        self.load(row(), row("S2", sold_on="2025-05-01", category="Office", country="United States"))
        self.assertEqual(report(self.db, date(2024,5,1), date(2024,5,1), "Living Room", "Canada")["summary"]["sales"], 1)
        self.assertEqual(report(self.db, category="Office", country="United States")["summary"]["sales"], 1)

    def test_no_match_null_rate(self):
        self.load(row())
        s = report(self.db, country="nowhere")["summary"]
        self.assertEqual(s["sales"], 0)
        self.assertEqual(s["net_cents"], 0)
        self.assertIsNone(s["avg_sale_cents"])
        self.assertIsNone(s["discount_pct"])

    def test_invalid_date_range(self):
        with self.assertRaises(ValueError):
            report(self.db, date(2025,1,1), date(2024,1,1))

    def test_sql_injection_is_literal(self):
        self.load(row())
        self.assertEqual(report(self.db, category="' OR 1=1 --")["summary"]["sales"], 0)
        self.assertEqual(report(self.db)["summary"]["sales"], 1)

    def test_exact_file_replay(self):
        f = self.write("source.csv", row())
        first = ingest(self.db, f)
        replay = ingest(self.db, f)
        self.assertEqual(first["status"], "committed")
        self.assertEqual((replay["status"], replay["rows_skipped"], replay["rows_inserted"]), ("replayed", 1, 0))
        self.assertEqual(report(self.db)["summary"]["sales"], 1)
        self.assertTrue(evaluate(self.db)["passed"])

    def test_mixed_overlap_insert_and_skip(self):
        self.load(row())
        second = self.load(row(), row("S2"), name="second.csv")
        self.assertEqual((second["rows_inserted"],second["rows_skipped"]),(1,1))

    def test_conflicting_event_rolls_back_all(self):
        self.load(row())
        with self.assertRaisesRegex(ContractError, "CONFLICTING_EXISTING_SALE"):
            self.load(row("NEW"), row(gross_cents=99999), name="conflict.csv")
        self.assertEqual(report(self.db)["summary"]["sales"], 1)
        self.assertEqual(evaluate(self.db)["counts"]["raw_sale"], 1)

    def test_concurrent_same_file(self):
        f = self.write("source.csv", row())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: ingest(self.db, f), range(2)))
        self.assertEqual(sorted(x["status"] for x in results), ["committed", "replayed"])
        self.assertEqual(evaluate(self.db)["counts"]["fact_sales"], 1)

    def test_snapshot_dimension_preserves_history(self):
        self.load(row(), row("S2", city="Vancouver", region="West", state="British Columbia",
                              product_type="Sectional Sofa"))
        q = evaluate(self.db)
        self.assertEqual(q["counts"]["dim_customer"], 2)
        self.assertEqual(q["counts"]["dim_product"], 2)
        self.assertEqual(report(self.db)["summary"]["customers"], 1)
        self.assertEqual(report(self.db)["summary"]["products"], 1)
        with connect(self.db, readonly=True) as db:
            result = dict(db.execute("SELECT source_sale_id,city FROM sales_detail"))
        self.assertEqual(result, {"S1":"Toronto", "S2":"Vancouver"})

    def test_snapshot_reuse(self):
        self.load(row(), row("S2"))
        q = evaluate(self.db)
        self.assertEqual(q["counts"]["dim_customer"], 1)
        self.assertEqual(q["counts"]["dim_product"], 1)

    def test_bad_date(self):
        self.reject([row(sold_on="2025-02-29")], "INVALID_SOLD_ON")

    def test_invalid_quantity(self):
        self.reject([row(quantity=0)], "INVALID_QUANTITY")

    def test_negative_money(self):
        self.reject([row(gross_cents=-1)], "INVALID_GROSS_CENTS")

    def test_decimal_cents_rejected(self):
        self.reject([row(gross_cents="100.1")], "INVALID_GROSS_CENTS")

    def test_discount_exceeds_gross(self):
        self.reject([row(discount_cents=10001)], "DISCOUNT_EXCEEDS_GROSS")

    def test_unsupported_currency(self):
        self.reject([row(currency="CAD")], "UNSUPPORTED_CURRENCY")

    def test_id_required(self):
        self.reject([row(sale_id=" ")], "INVALID_SALE_ID")

    def test_control_char(self):
        self.reject([row(city="bad\x01city")], "INVALID_CITY")

    def test_duplicate_in_same_batch_rolls_back(self):
        self.reject([row(), row()], "DUPLICATE_IN_BATCH")

    def test_late_invalid_row_rolls_back(self):
        self.reject([row(), row("S2", quantity=0)], "INVALID_QUANTITY")
        self.assertEqual(evaluate(self.db)["counts"]["dim_customer"], 0)

    def test_empty_batch(self):
        self.reject([], "EMPTY_BATCH")

    def test_wrong_header(self):
        path = self.root / "bad.csv"
        path.write_text("unexpected,header\n1,2\n")
        with self.assertRaisesRegex(ContractError, "SCHEMA_MISMATCH"):
            ingest(self.db, path)

    def test_extra_column(self):
        path = self.write("bad.csv", row())
        path.write_text(path.read_text().rstrip()+" ,extra\n")
        with self.assertRaisesRegex(ContractError, "COLUMN_COUNT"):
            ingest(self.db, path)

    def test_bad_utf8(self):
        path = self.root / "bad.csv"
        path.write_bytes(b"\xff")
        with self.assertRaisesRegex(ContractError, "INVALID_CSV"):
            ingest(self.db, path)

    def test_zero_revenue_defined(self):
        self.load(row(gross_cents=0, discount_cents=0))
        self.assertEqual(report(self.db)["summary"]["net_cents"], 0)
        self.assertIsNone(report(self.db)["summary"]["discount_pct"])

    def test_db_constraints_and_readonly(self):
        self.load(row())
        with connect(self.db, readonly=True) as db, self.assertRaises(sqlite3.OperationalError):
            db.execute("DELETE FROM fact_sales")
        with connect(self.db) as db, self.assertRaises(sqlite3.IntegrityError):
            db.execute("UPDATE fact_sales SET quantity=-1")

    def test_tampering_detected(self):
        self.load(row())
        with connect(self.db) as db:
            db.execute("UPDATE fact_sales SET gross_cents=99999")
            db.commit()
        q = evaluate(self.db)
        self.assertFalse(q["passed"])
        self.assertFalse(next(c for c in q["checks"] if c["name"]=="raw_to_fact_attributes")["passed"])

    def test_raw_payload_hash_detected(self):
        self.load(row())
        with connect(self.db) as db:
            db.execute("UPDATE raw_sale SET payload_json='{}'")
            db.commit()
        self.assertFalse(next(c for c in evaluate(self.db)["checks"] if c["name"]=="raw_payload_hashes")["passed"])

    def test_stale_running_run_detected(self):
        with connect(self.db) as db:
            db.execute("INSERT INTO ingest_run(run_id,source_sha256,started_at,status) VALUES(?,?,?,'running')",
                       ("orphan","a"*64,"2025-01-01"))
            db.commit()
        self.assertFalse(evaluate(self.db)["passed"])

    def test_backup_restores_exact_metrics(self):
        self.load(row())
        dest = self.root/"backup.db"
        self.assertTrue(backup(self.db, dest)["passed"])
        self.assertEqual(report(self.db)["summary"], report(dest)["summary"])
        self.load(row("S2"))
        self.assertEqual(report(dest)["summary"]["sales"], 1)
        with self.assertRaises(FileExistsError):
            backup(self.db, dest)

    def test_export_and_exclusive_creation(self):
        self.load(row())
        dest = self.root/"monthly.csv"
        self.assertEqual(export_monthly(self.db,dest),1)
        with dest.open() as f:
            exported = list(csv.DictReader(f))
        self.assertEqual(exported[0]["net_cents"],"9500")
        self.assertEqual(exported[0]["month"],"2024-05")
        with self.assertRaises(FileExistsError):
            export_monthly(self.db,dest)

    def test_generator_deterministic(self):
        a,b = self.root/"a.csv",self.root/"b.csv"
        generate(a,100,42);generate(b,100,42)
        self.assertEqual(a.read_bytes(),b.read_bytes())
        self.assertEqual(ingest(self.db,a)["rows_inserted"],100)
        self.assertTrue(evaluate(self.db)["passed"])

    def test_full_seed_independent_reconciliation(self):
        f = generate(self.root/"large.csv",5000,42)
        with f.open() as handle:
            raw = list(csv.DictReader(handle))
        ingest(self.db,f)
        s = report(self.db)["summary"]
        self.assertEqual(s["sales"],len(raw))
        self.assertEqual(s["units"],sum(int(x["quantity"]) for x in raw))
        self.assertEqual(s["net_cents"],sum(int(x["gross_cents"])-int(x["discount_cents"]) for x in raw))
        self.assertEqual(s["customers"],len({x["customer_id"] for x in raw}))
        self.assertTrue(evaluate(self.db)["passed"])

    def test_legacy_requires_assumption(self):
        with self.assertRaisesRegex(ValueError,"Explicit demo assumptions"):
            export_legacy(self.root/"legacy.csv")

    def test_legacy_actual_100_rows(self):
        f = self.root/"legacy.csv"
        self.assertEqual(export_legacy(f,assume_income_is_gross=True,currency="USD"),100)
        self.assertEqual(ingest(self.db,f)["rows_inserted"],100)
        s=report(self.db)["summary"]
        self.assertEqual((s["sales"],s["units"],s["gross_cents"],s["discount_cents"],s["net_cents"]),
                         (100,479,51680000,2345600,49334400))
        self.assertTrue(evaluate(self.db)["passed"])


if __name__ == "__main__":
    unittest.main()
