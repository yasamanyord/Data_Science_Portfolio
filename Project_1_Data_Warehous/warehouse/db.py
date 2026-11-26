"""Database lifecycle and atomic, idempotent ingestion."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
from uuid import uuid4

from .contract import ContractError, read_sales, MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sql" / "001_warehouse.sql"
DEFAULT_DB = ROOT / "runtime" / "warehouse.sqlite3"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path, readonly=False):
    path = Path(path).resolve()
    if readonly:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    else:
        db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    if readonly:
        db.execute("PRAGMA query_only = ON")
    try:
        yield db
    finally:
        db.close()


def init(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version == 1:
            return
        if version != 0 or db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
            raise RuntimeError("Unsupported or nonempty database; use a dedicated warehouse DB")
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA.read_text() +
                         "\nPRAGMA user_version=1;\nCOMMIT;")


def assert_version(db):
    if db.execute("PRAGMA user_version").fetchone()[0] != 1:
        raise RuntimeError("Warehouse not initialized or unsupported schema version")


def dimension_key(db, table, key, fields, values):
    # All identifiers are internal constants at call sites, never user input.
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    predicate = " AND ".join(f"{field}=?" for field in fields)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", values)
    return db.execute(f"SELECT {key} FROM {table} WHERE {predicate}", values).fetchone()[0]


def load_one(db, run_id, line, sale):
    digest = sale.digest()
    previous = db.execute("SELECT payload_sha256 FROM raw_sale WHERE source_sale_id=?",
                          (sale.sale_id,)).fetchone()
    if previous:
        if previous[0] != digest:
            raise ContractError(f"line {line}: CONFLICTING_EXISTING_SALE")
        return False
    d = date.fromisoformat(sale.sold_on)
    date_key = int(d.strftime("%Y%m%d"))
    db.execute("INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
               (date_key, d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month, d.day))
    product = dimension_key(db, "dim_product", "product_key",
                            ("product_id", "product_type", "category", "material"),
                            (sale.product_id, sale.product_type, sale.category, sale.material))
    customer = dimension_key(db, "dim_customer", "customer_key",
                             ("customer_id", "city", "region", "state", "country"),
                             (sale.customer_id, sale.city, sale.region, sale.state, sale.country))
    raw_id = db.execute(
        "INSERT INTO raw_sale(source_sale_id,run_id,line_number,payload_sha256,payload_json) VALUES(?,?,?,?,?)",
        (sale.sale_id, run_id, line, digest, sale.canonical())).lastrowid
    db.execute("""INSERT INTO fact_sales(raw_id,date_key,product_key,customer_key,
                   quantity,gross_cents,discount_cents,currency) VALUES(?,?,?,?,?,?,?,?)""",
               (raw_id, date_key, product, customer, sale.quantity, sale.gross_cents,
                sale.discount_cents, sale.currency))
    return True


def ingest(path, source):
    """Persist a run; all validated rows and run status commit together or roll back."""
    if not Path(path).is_file():
        raise RuntimeError("Warehouse not initialized; run init first")
    with Path(source).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ContractError("FILE_TOO_LARGE (rejected before audit; no full-file hash)")
    source_sha = sha256(data).hexdigest()
    run_id = uuid4().hex
    seen = inserted = skipped = 0
    with connect(path) as db:
        assert_version(db)
        db.execute("INSERT INTO ingest_run(run_id,source_sha256,started_at,status) VALUES(?,?,?,'running')",
                   (run_id, source_sha, now()))
        db.commit()
        try:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("""SELECT rows_seen FROM ingest_run
                                 WHERE source_sha256=? AND status='committed' LIMIT 1""",
                               (source_sha,)).fetchone()
            if prior:
                seen = skipped = prior[0]
                status = "replayed"
            else:
                for line, sale in read_sales(data):
                    seen += 1
                    if load_one(db, run_id, line, sale):
                        inserted += 1
                    else:
                        skipped += 1
                status = "committed"
            db.execute("""UPDATE ingest_run SET finished_at=?,status=?,rows_seen=?,
                           rows_inserted=?,rows_skipped=? WHERE run_id=?""",
                       (now(), status, seen, inserted, skipped, run_id))
            db.commit()
        except (ContractError, sqlite3.Error) as exc:
            db.rollback()
            error = str(exc) if isinstance(exc, ContractError) else "DATABASE_WRITE_FAILED"
            db.execute("""UPDATE ingest_run SET finished_at=?,status='rejected',
                          rows_seen=?, error_code=? WHERE run_id=?""",
                       (now(), seen, error, run_id))
            db.commit()
            raise ContractError(f"run {run_id}: {error}") from None
        return dict(db.execute("SELECT * FROM ingest_run WHERE run_id=?", (run_id,)).fetchone())
