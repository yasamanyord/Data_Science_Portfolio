"""One-time adapter for the original trusted, bundled SQL sample (not arbitrary SQL)."""
from contextlib import closing
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3

from .contract import FIELDS
from .db import ROOT


def cents(value):
    amount = Decimal(str(value)) * 100
    if amount != amount.to_integral_value():
        raise ValueError("legacy monetary value has more than two decimal places")
    return int(amount)


def export_legacy(destination, *, assume_income_is_gross=False, currency=None):
    if not assume_income_is_gross or currency != "USD":
        raise ValueError("Explicit demo assumptions required: --assume-income-is-gross --currency USD")
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("PRAGMA foreign_keys=ON")
        # Only execute the two existing, trusted project files. The CLI accepts no SQL path.
        for filename in ("1_Schema_Definition.sql", "2_Sample_Data_Inserts.sql"):
            db.executescript((ROOT / filename).read_text(encoding="utf-8"))
        rows = db.execute("""SELECT s.IdSale,t.Day,t.Month,t.Year,f.IdFurniture,f.Type,
                   f.Category,f.Material,c.IdCustomer,c.City,c.Region,c.State,c.Country,
                   s.Quantity,s.Income,s.Discount
                   FROM Sales s JOIN Time t USING(IdTime) JOIN Furniture f USING(IdFurniture)
                   JOIN Customer c USING(IdCustomer) ORDER BY s.IdSale""").fetchall()
    months = {name: i for i, name in enumerate(("January","February","March","April","May","June",
                                               "July","August","September","October","November","December"), 1)}
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(FIELDS)
        for sale, day, month, year, product, ptype, category, material, customer, city, region, state, country, qty, income, discount in rows:
            writer.writerow([f"LEGACY-S-{sale}", date(year, months[month], day).isoformat(),
                             f"LEGACY-P-{product}", ptype, category, material,
                             f"LEGACY-C-{customer}", city, region, state, country, qty,
                             cents(income), cents(discount), currency])
    return len(rows)
