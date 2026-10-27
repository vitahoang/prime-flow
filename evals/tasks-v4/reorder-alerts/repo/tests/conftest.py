import csv
import json
from datetime import date
from pathlib import Path

import pytest

from stockroom.store import MOVEMENT_FIELDS, load

TODAY = date(2026, 10, 15)

SHOPS = [
    {"code": "HAR", "name": "Harbour"},
    {"code": "MKT", "name": "Market Street"},
    {"code": "STN", "name": "Station Road"},
]
ITEMS = [
    {"sku": "OAT-1L", "name": "Oat milk 1L", "unit": "carton", "supplier": "green-valley",
     "category": "dairy", "min_stock": 24},
    {"sku": "CRD-SHEET", "name": "Croissant dough sheet", "unit": "sheet", "supplier": "laminata",
     "category": "bakery", "min_stock": 40},
]
SUPPLIERS = [
    {"id": "green-valley", "name": "Green Valley Dairy", "lead_time_days": 2,
     "items": [{"sku": "OAT-1L", "case_size": 12, "unit_cost": 1.5}]},
    {"id": "laminata", "name": "Laminata", "lead_time_days": 4,
     "items": [{"sku": "CRD-SHEET", "case_size": 20, "unit_cost": 0.8}]},
]
MOVEMENTS = [
    ("2026-10-01", "HAR", "OAT-1L", "delivery", 48, "D1", ""),
    ("2026-10-01", "MKT", "OAT-1L", "delivery", 36, "D2", ""),
    ("2026-10-02", "HAR", "OAT-1L", "sale", 10, "", ""),
    ("2026-10-03", "HAR", "OAT-1L", "waste", 2, "", "out of date"),
    ("2026-10-10", "HAR", "OAT-1L", "transfer_out", 6, "T1", ""),
    ("2026-10-10", "STN", "OAT-1L", "transfer_in", 6, "T1", ""),
    ("2026-10-12", "MKT", "OAT-1L", "return", 12, "R1", "crushed case"),
    ("2026-10-14", "MKT", "OAT-1L", "sale", 5, "", ""),
    ("2026-10-01", "MKT", "CRD-SHEET", "delivery", 100, "D3", ""),
    ("2026-10-13", "MKT", "CRD-SHEET", "sale", 30, "", ""),
]
ORDERS = [
    {"id": "PO-0001", "supplier": "green-valley", "shop": "MKT", "status": "open",
     "ordered": "2026-10-13", "expected": "2026-10-14", "lines": [{"sku": "OAT-1L", "qty": 24}]},
    {"id": "PO-0002", "supplier": "laminata", "shop": "MKT", "status": "received",
     "ordered": "2026-09-28", "expected": "2026-10-01", "lines": [{"sku": "CRD-SHEET", "qty": 100}]},
    {"id": "PO-0003", "supplier": "green-valley", "shop": "HAR", "status": "cancelled",
     "ordered": "2026-10-11", "lines": [{"sku": "OAT-1L", "qty": 12}]},
]


def write_data(root: Path, shops=SHOPS, items=ITEMS, suppliers=SUPPLIERS,
               movements=MOVEMENTS, orders=ORDERS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "shops.json").write_text(json.dumps(shops))
    (root / "items.json").write_text(json.dumps(items))
    (root / "suppliers.json").write_text(json.dumps(suppliers))
    with (root / "movements.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(MOVEMENT_FIELDS)
        w.writerows(movements)
    if orders is not None:
        (root / "purchase_orders.json").write_text(json.dumps(orders))
    return root


@pytest.fixture
def data_dir(tmp_path):
    return write_data(tmp_path / "data")


@pytest.fixture
def inv(data_dir):
    return load(data_dir)


@pytest.fixture
def today(monkeypatch):
    monkeypatch.setenv("STOCKROOM_TODAY", TODAY.isoformat())
    return TODAY
