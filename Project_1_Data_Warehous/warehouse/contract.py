"""Strict, versioned sale-event CSV contract."""
from dataclasses import dataclass, asdict
from datetime import date
from hashlib import sha256
import csv
import io
import json
import re

FIELDS = (
    "sale_id", "sold_on", "product_id", "product_type", "category", "material",
    "customer_id", "city", "region", "state", "country", "quantity",
    "gross_cents", "discount_cents", "currency",
)
MAX_BYTES = 20_000_000
MAX_ROWS = 100_000


class ContractError(ValueError):
    """Safe error: never includes customer input values."""


@dataclass(frozen=True)
class Sale:
    sale_id: str
    sold_on: str
    product_id: str
    product_type: str
    category: str
    material: str
    customer_id: str
    city: str
    region: str
    state: str
    country: str
    quantity: int
    gross_cents: int
    discount_cents: int
    currency: str

    def canonical(self):
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def digest(self):
        return sha256(self.canonical().encode("utf-8")).hexdigest()


def parse_sale(row, line):
    if set(row) != set(FIELDS) or any(v is None for v in row.values()):
        raise ContractError(f"line {line}: COLUMN_COUNT")
    values = {}
    for field in FIELDS:
        value = row[field].strip()
        if not value or len(value) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ContractError(f"line {line}: INVALID_{field.upper()}")
        values[field] = value
    for field in ("sale_id", "product_id", "customer_id"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", values[field]):
            raise ContractError(f"line {line}: INVALID_{field.upper()}")
    try:
        d = date.fromisoformat(values["sold_on"])
        if d.isoformat() != values["sold_on"] or not 2000 <= d.year <= 2100:
            raise ValueError
    except ValueError:
        raise ContractError(f"line {line}: INVALID_SOLD_ON") from None
    for field, low, high in (
        ("quantity", 1, 100000),
        ("gross_cents", 0, 10000000000),
        ("discount_cents", 0, 10000000000),
    ):
        value = values[field]
        if not re.fullmatch(r"[0-9]{1,11}", value) or not low <= int(value) <= high:
            raise ContractError(f"line {line}: INVALID_{field.upper()}")
        values[field] = int(value)
    if values["discount_cents"] > values["gross_cents"]:
        raise ContractError(f"line {line}: DISCOUNT_EXCEEDS_GROSS")
    if values["currency"] != "USD":
        raise ContractError(f"line {line}: UNSUPPORTED_CURRENCY")
    return Sale(**values)


def read_sales(data):
    """Strict header/rows. Duplicate sale IDs within a file are source errors."""
    if len(data) > MAX_BYTES:
        raise ContractError("FILE_TOO_LARGE")
    try:
        stream = io.StringIO(data.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != list(FIELDS):
            raise ContractError("SCHEMA_MISMATCH")
        seen = set()
        for i, row in enumerate(reader, 1):
            if i > MAX_ROWS:
                raise ContractError("TOO_MANY_ROWS")
            sale = parse_sale(row, reader.line_num)
            if sale.sale_id in seen:
                raise ContractError(f"line {reader.line_num}: DUPLICATE_IN_BATCH")
            seen.add(sale.sale_id)
            yield reader.line_num, sale
        if not seen:
            raise ContractError("EMPTY_BATCH")
    except (UnicodeError, csv.Error):
        raise ContractError("INVALID_CSV_ENCODING_OR_FORMAT") from None
