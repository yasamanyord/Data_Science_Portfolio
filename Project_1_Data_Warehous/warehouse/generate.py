"""Reproducible fictional source events, separate from the original SQL exercise."""
import csv
from datetime import date, timedelta
from pathlib import Path
import random

from .contract import FIELDS, MAX_ROWS

PRODUCTS = [
    ("Sofa", "Living Room", "Fabric", 54000),
    ("Armchair", "Living Room", "Leather", 32500),
    ("Coffee Table", "Living Room", "Wood", 18000),
    ("Bed", "Bedroom", "Wood", 62000),
    ("Wardrobe", "Bedroom", "Wood", 48000),
    ("Dresser", "Bedroom", "Wood", 24000),
    ("Dining Table", "Dining", "Wood", 40000),
    ("Dining Chair", "Dining", "Metal", 9500),
    ("Office Desk", "Office", "Metal", 32500),
    ("Office Chair", "Office", "Fabric", 23000),
]
LOCATIONS = [
    ("Toronto", "Central", "Ontario", "Canada"),
    ("Vancouver", "West", "British Columbia", "Canada"),
    ("Montreal", "East", "Quebec", "Canada"),
    ("Calgary", "West", "Alberta", "Canada"),
    ("Ottawa", "Central", "Ontario", "Canada"),
    ("Chicago", "Midwest", "Illinois", "United States"),
    ("New York", "East", "New York", "United States"),
    ("Seattle", "West", "Washington", "United States"),
]


def generate(path, rows=5000, seed=42, start_id=1):
    if not 1 <= rows <= MAX_ROWS or not 1 <= start_id <= 999999999:
        raise ValueError("rows or start_id out of range")
    rng = random.Random(seed)
    start = date(2024, 1, 1)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        for i in range(start_id, start_id + rows):
            product_index = rng.randrange(len(PRODUCTS))
            product, category, material, unit = PRODUCTS[product_index]
            customer = rng.randint(1, 250)
            city, region, state, country = LOCATIONS[(customer - 1) % len(LOCATIONS)]
            sold_on = start + timedelta(days=rng.randrange(731))
            quantity = rng.randint(1, 20)
            gross = unit * quantity
            discount = gross * rng.choice([0, 0, 5, 10, 15]) // 100
            writer.writerow([f"S-{i:09d}", sold_on.isoformat(), f"P-{product_index + 1:03d}",
                             product, category, material, f"C-{customer:04d}", city, region,
                             state, country, quantity, gross, discount, "USD"])
    return path
