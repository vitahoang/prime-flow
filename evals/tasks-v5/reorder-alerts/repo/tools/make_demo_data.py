"""Regenerate the demo data directory (``data/``) with made-up but realistic numbers.

    python tools/make_demo_data.py [OUT_DIR] [--end YYYY-MM-DD] [--days N]

Deterministic: the same arguments always give the same files.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stockroom.store import MOVEMENT_FIELDS  # noqa: E402

SHOPS = [
    {"code": "HAR", "name": "Harbour", "opened": "2019-04-01"},
    {"code": "MKT", "name": "Market Street", "opened": "2021-09-13"},
    {"code": "STN", "name": "Station Road", "opened": "2023-03-06"},
]

SUPPLIERS = [
    {"id": "green-valley", "name": "Green Valley Dairy", "lead_time_days": 2,
     "contact": "orders@greenvalley.example", "delivery_days": ["tue", "fri"],
     "items": [{"sku": "OAT-1L", "case_size": 12, "unit_cost": 1.65},
               {"sku": "MILK-2L", "case_size": 6, "unit_cost": 1.40},
               {"sku": "BUTTER-1K", "case_size": 10, "unit_cost": 7.20}]},
    {"id": "laminata", "name": "Laminata Bakery Supplies", "lead_time_days": 4,
     "contact": "trade@laminata.example", "delivery_days": ["mon", "thu"], "on_hold": True,
     "items": [{"sku": "CRD-SHEET", "case_size": 20, "unit_cost": 0.85},
               {"sku": "PAIN-CHOC", "case_size": 10, "unit_cost": 6.50}]},
    {"id": "millers", "name": "Hollow Mill", "lead_time_days": 5,
     "contact": "sales@hollowmill.example", "delivery_days": ["wed"],
     "items": [{"sku": "FLOUR-16", "case_size": 1, "unit_cost": 14.00}]},
    {"id": "roastworks", "name": "Roastworks Coffee", "lead_time_days": 3,
     "contact": "wholesale@roastworks.example",
     "delivery_days": ["mon", "tue", "wed", "thu", "fri"],
     "items": [{"sku": "BEANS-HOUSE", "case_size": 6, "unit_cost": 16.00},
               {"sku": "BEANS-DECAF", "case_size": 6, "unit_cost": 17.50}]},
    {"id": "packright", "name": "PackRight", "lead_time_days": 7,
     "contact": "orders@packright.example", "delivery_days": ["thu"],
     "items": [{"sku": "CUP-12", "case_size": 20, "unit_cost": 4.10},
               {"sku": "LID-12", "case_size": 20, "unit_cost": 2.30}]},
]

# sku, name, unit, supplier, category, min_stock, daily sales at Harbour
ITEMS = [
    ("OAT-1L", "Oat milk 1L", "carton", "green-valley", "dairy", 24, 9),
    ("MILK-2L", "Whole milk 2L", "bottle", "green-valley", "dairy", 30, 11),
    ("BUTTER-1K", "Butter 1kg", "block", "green-valley", "dairy", 20, 2),
    ("CRD-SHEET", "Croissant dough sheet", "sheet", "laminata", "bakery", 40, 14),
    ("PAIN-CHOC", "Pain au chocolat dough", "tray", "laminata", "bakery", 10, 2),
    ("FLOUR-16", "Strong flour 16kg", "sack", "millers", "bakery", 3, 0.4),
    ("BEANS-HOUSE", "House espresso beans 1kg", "bag", "roastworks", "coffee", 12, 3),
    ("BEANS-DECAF", "Decaf beans 1kg", "bag", "roastworks", "coffee", 4, 0.5),
    ("CUP-12", "12oz cups (sleeve of 50)", "sleeve", "packright", "packaging", 40, 5),
    ("LID-12", "12oz lids (sleeve of 50)", "sleeve", "packright", "packaging", 40, 5),
]

SHOP_FACTOR = {"HAR": 1.0, "MKT": 1.4, "STN": 0.7}


def build(out: Path, end: date, days: int, seed: int = 7) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    (out / "shops.json").write_text(json.dumps(SHOPS, indent=2) + "\n")
    (out / "suppliers.json").write_text(json.dumps(SUPPLIERS, indent=2) + "\n")
    (out / "items.json").write_text(json.dumps([
        {"sku": s, "name": n, "unit": u, "supplier": sup, "category": c, "min_stock": mn}
        for s, n, u, sup, c, mn, _ in ITEMS
    ], indent=2) + "\n")

    start = end - timedelta(days=days - 1)
    rows = []
    stock = {}
    for shop in SHOP_FACTOR:
        for sku, *_rest, rate in ITEMS:
            opening = round(rate * SHOP_FACTOR[shop] * 10) + 5
            stock[(shop, sku)] = opening
            rows.append([start.isoformat(), shop, sku, "delivery", opening, "opening", ""])

    for n in range(days):
        day = start + timedelta(days=n)
        for shop, factor in SHOP_FACTOR.items():
            for sku, _name, _unit, sup, cat, _mn, rate in ITEMS:
                key = (shop, sku)
                sold = min(stock[key], max(0, round(rng.gauss(rate * factor, rate * factor * 0.3))))
                if sold:
                    stock[key] -= sold
                    rows.append([day.isoformat(), shop, sku, "sale", sold, "", ""])
                if cat in ("dairy", "bakery") and stock[key] > 0 and rng.random() < 0.15:
                    binned = min(stock[key], rng.randint(1, 3))
                    stock[key] -= binned
                    rows.append([day.isoformat(), shop, sku, "waste", binned, "", "out of date"])
                if day.weekday() in (0, 3) and stock[key] < rate * factor * 6:
                    qty = round(rate * factor * 7) + 4
                    stock[key] += qty
                    rows.append([day.isoformat(), shop, sku, "delivery", qty, f"D{day:%m%d}{shop}", ""])
        if n % 9 == 4:
            sku = rng.choice(["OAT-1L", "CRD-SHEET", "MILK-2L"])
            qty = rng.randint(4, 12)
            if stock[("HAR", sku)] > qty:
                stock[("HAR", sku)] -= qty
                stock[("STN", sku)] += qty
                ref = f"T{day:%m%d}"
                rows.append([day.isoformat(), "HAR", sku, "transfer_out", qty, ref, "to Station Road"])
                rows.append([day.isoformat(), "STN", sku, "transfer_in", qty, ref, "from Harbour"])
        if n % 17 == 11 and stock[("MKT", "OAT-1L")] > 6:
            stock[("MKT", "OAT-1L")] -= 6
            rows.append([day.isoformat(), "MKT", "OAT-1L", "return", 6, "R-GV", "crushed case"])

    with (out / "movements.csv").open("w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(MOVEMENT_FIELDS)
        writer.writerows(rows)

    orders = [
        {"id": "PO-0141", "supplier": "laminata", "shop": "MKT", "status": "received",
         "ordered": (end - timedelta(days=9)).isoformat(),
         "expected": (end - timedelta(days=5)).isoformat(),
         "lines": [{"sku": "CRD-SHEET", "qty": 120}]},
        {"id": "PO-0142", "supplier": "green-valley", "shop": "HAR", "status": "cancelled",
         "ordered": (end - timedelta(days=4)).isoformat(),
         "expected": (end - timedelta(days=2)).isoformat(),
         "lines": [{"sku": "OAT-1L", "qty": 48}]},
        {"id": "PO-0143", "supplier": "green-valley", "shop": "MKT", "status": "open",
         "ordered": (end - timedelta(days=1)).isoformat(),
         "expected": (end + timedelta(days=1)).isoformat(),
         "lines": [{"sku": "OAT-1L", "qty": 36}, {"sku": "MILK-2L", "qty": 24}]},
        {"id": "PO-0144", "supplier": "packright", "shop": "STN", "status": "open",
         "ordered": (end - timedelta(days=3)).isoformat(),
         "expected": (end + timedelta(days=4)).isoformat(),
         "lines": [{"sku": "CUP-12", "qty": 40}, {"sku": "LID-12", "qty": 40}]},
    ]
    (out / "purchase_orders.json").write_text(json.dumps(orders, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", nargs="?", default="data")
    parser.add_argument("--end", default="2026-10-15")
    parser.add_argument("--days", type=int, default=56)
    args = parser.parse_args()
    build(Path(args.out), date.fromisoformat(args.end), args.days)
    print(f"wrote demo data to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
