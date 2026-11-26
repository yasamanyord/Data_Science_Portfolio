"""Independent reconciliation checks: raw source -> dimensions -> fact -> mart."""
from hashlib import sha256
import json

from .db import assert_version, connect


def evaluate(path):
    with connect(path, readonly=True) as db:
        assert_version(db)
        db.execute("BEGIN")
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("raw_sale", "fact_sales", "dim_date", "dim_customer", "dim_product", "ingest_run")}
        checks = []

        def check(name, failures):
            checks.append({"name": name, "failures": failures, "passed": failures == 0})

        check("sqlite_integrity", sum(row[0] != "ok" for row in db.execute("PRAGMA integrity_check")))
        check("foreign_keys", len(db.execute("PRAGMA foreign_key_check").fetchall()))
        check("raw_fact_one_to_one", abs(counts["raw_sale"] - counts["fact_sales"]) +
              db.execute("SELECT COUNT(*) FROM raw_sale r LEFT JOIN fact_sales f ON f.raw_id=r.raw_id WHERE f.raw_id IS NULL").fetchone()[0])
        check("mart_fact_count", abs(counts["fact_sales"] - db.execute("SELECT COUNT(*) FROM sales_detail").fetchone()[0]))
        check("money_and_quantity", db.execute("""SELECT COUNT(*) FROM fact_sales WHERE
              quantity <= 0 OR gross_cents < 0 OR discount_cents < 0 OR discount_cents > gross_cents
              OR net_cents != gross_cents - discount_cents OR currency != 'USD'""").fetchone()[0])
        check("committed_run_reconciliation", db.execute("""
              SELECT COUNT(*) FROM ingest_run i LEFT JOIN (
                  SELECT run_id,COUNT(*) AS n FROM raw_sale GROUP BY run_id
              ) r USING(run_id)
              WHERE (i.status='committed' AND (i.rows_seen != i.rows_inserted+i.rows_skipped
                   OR i.rows_inserted != COALESCE(r.n,0)))
                 OR (i.status!='committed' AND COALESCE(r.n,0) != 0)
                 OR (i.status='replayed' AND (i.rows_inserted != 0 OR i.rows_skipped != i.rows_seen))
                 OR (i.status='running')""").fetchone()[0])
        bad_hash = bad_payload = 0
        for row in db.execute("""SELECT r.payload_json,r.payload_sha256, s.*
                                 FROM raw_sale r JOIN sales_detail s USING(source_sale_id)"""):
            raw = row["payload_json"]
            bad_hash += sha256(raw.encode("utf-8")).hexdigest() != row["payload_sha256"]
            try:
                expected = json.loads(raw)
                matches = {"sale_id": row["source_sale_id"], "sold_on": row["full_date"]}
                for key in ("product_id", "product_type", "category", "material", "customer_id",
                            "city", "region", "state", "country", "quantity", "gross_cents",
                            "discount_cents", "currency"):
                    matches[key] = row[key]
                bad_payload += expected != matches
            except (ValueError, TypeError):
                bad_payload += 1
        check("raw_payload_hashes", bad_hash)
        check("raw_to_fact_attributes", bad_payload)
        check("date_attributes", db.execute("""SELECT COUNT(*) FROM dim_date WHERE
              date_key != CAST(replace(full_date,'-','') AS INTEGER)
              OR year != CAST(substr(full_date,1,4) AS INTEGER)
              OR month != CAST(substr(full_date,6,2) AS INTEGER)
              OR day != CAST(substr(full_date,9,2) AS INTEGER)
              OR quarter != ((month-1)/3)+1""").fetchone()[0])
        check("money_reconciliation", db.execute("""SELECT CASE WHEN
              COALESCE(SUM(gross_cents),0)-COALESCE(SUM(discount_cents),0)=COALESCE(SUM(net_cents),0)
              THEN 0 ELSE 1 END FROM fact_sales""").fetchone()[0])
        return {"passed": all(c["passed"] for c in checks), "checks": checks, "counts": counts}


def backup(source, destination):
    """Consistent SQLite online backup; verify copied warehouse, never overwrite."""
    from pathlib import Path
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("backup destination must differ from source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.touch(exist_ok=False)
    try:
        with connect(source, readonly=True) as src:
            assert_version(src)
            with connect(destination) as dest:
                src.backup(dest)
        result = evaluate(destination)
        if not result["passed"]:
            raise ValueError("backup failed reconciliation")
        return result
    except Exception:
        destination.unlink(missing_ok=True)
        raise
