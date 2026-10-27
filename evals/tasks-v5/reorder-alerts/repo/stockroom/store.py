"""Read and write the data directory.

Layout of a data directory::

    shops.json            [{"code", "name", "opened"}]
    items.json            [{"sku", "name", "unit", "supplier", "category", "min_stock"}]
    suppliers.json        [{"id", "name", "lead_time_days", "contact",
                            "items": [{"sku", "case_size", "unit_cost"}]}]
    movements.csv         date,shop,sku,type,qty,ref,note
    purchase_orders.json  [{"id", "supplier", "shop", "status", "ordered",
                            "expected", "lines": [{"sku", "qty"}]}]

movements.csv is appended to by the POS export every night, so it is kept as
CSV; everything else is edited by hand and is JSON.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import (
    Item,
    Movement,
    MovementType,
    POLine,
    POStatus,
    PurchaseOrder,
    Shop,
    Supplier,
    SupplierItem,
)

MOVEMENT_FIELDS = ["date", "shop", "sku", "type", "qty", "ref", "note"]


class DataError(Exception):
    """The data directory is missing a file or a record is malformed."""


@dataclass
class Inventory:
    shops: Dict[str, Shop] = field(default_factory=dict)
    items: Dict[str, Item] = field(default_factory=dict)
    suppliers: Dict[str, Supplier] = field(default_factory=dict)
    movements: List[Movement] = field(default_factory=list)
    purchase_orders: List[PurchaseOrder] = field(default_factory=list)

    def item(self, sku: str) -> Item:
        try:
            return self.items[sku.upper()]
        except KeyError:
            raise DataError(f"unknown SKU {sku!r}") from None

    def shop(self, code: str) -> Shop:
        try:
            return self.shops[code.upper()]
        except KeyError:
            known = ", ".join(sorted(self.shops)) or "none"
            raise DataError(f"unknown shop {code!r} (known: {known})") from None

    def supplier_for(self, sku: str) -> Supplier:
        item = self.item(sku)
        try:
            return self.suppliers[item.supplier]
        except KeyError:
            raise DataError(f"{item.sku}: unknown supplier {item.supplier!r}") from None

    def shop_codes(self) -> List[str]:
        return sorted(self.shops)


def parse_date(value: str, what: str = "date") -> date:
    try:
        return date.fromisoformat(value.strip())
    except (AttributeError, ValueError):
        raise DataError(f"bad {what}: {value!r} (expected YYYY-MM-DD)") from None


def _optional_date(value: Optional[str], what: str) -> Optional[date]:
    if value in (None, ""):
        return None
    return parse_date(value, what)


def _read_json(path: Path) -> list:
    if not path.exists():
        raise DataError(f"missing {path.name} in {path.parent}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name}: {exc}") from None
    if not isinstance(data, list):
        raise DataError(f"{path.name}: expected a list")
    return data


def load_shops(path: Path) -> Dict[str, Shop]:
    shops = {}
    for row in _read_json(path):
        code = row["code"].strip().upper()
        shops[code] = Shop(code, row.get("name", code), _optional_date(row.get("opened"), "opened"))
    return shops


def load_items(path: Path) -> Dict[str, Item]:
    items = {}
    for row in _read_json(path):
        try:
            item = Item(
                sku=row["sku"],
                name=row.get("name", row["sku"]),
                unit=row.get("unit", "each"),
                supplier=row.get("supplier", ""),
                category=row.get("category", "other"),
                min_stock=int(row.get("min_stock", 0)),
            )
        except (KeyError, ValueError) as exc:
            raise DataError(f"items.json: {exc}") from None
        items[item.sku] = item
    return items


def load_suppliers(path: Path) -> Dict[str, Supplier]:
    suppliers = {}
    for row in _read_json(path):
        entries = {}
        for entry in row.get("items", []):
            si = SupplierItem(
                sku=entry["sku"],
                case_size=int(entry.get("case_size", 1)),
                unit_cost=float(entry.get("unit_cost", 0.0)),
            )
            entries[si.sku] = si
        suppliers[row["id"]] = Supplier(
            id=row["id"],
            name=row.get("name", row["id"]),
            lead_time_days=int(row.get("lead_time_days", 1)),
            contact=row.get("contact", ""),
            items=entries,
        )
    return suppliers


def parse_movement(row: Dict[str, str], line_no: int = 0) -> Movement:
    where = f"movements.csv line {line_no}" if line_no else "movement"
    try:
        mtype = MovementType(row["type"].strip().lower())
    except (KeyError, ValueError):
        raise DataError(f"{where}: unknown movement type {row.get('type')!r}") from None
    try:
        qty = float(row["qty"])
    except (KeyError, ValueError):
        raise DataError(f"{where}: bad qty {row.get('qty')!r}") from None
    if qty < 0:
        raise DataError(f"{where}: qty must be positive; the type gives the direction")
    return Movement(
        date=parse_date(row["date"], f"date on {where}"),
        shop=row["shop"].strip().upper(),
        sku=row["sku"].strip().upper(),
        type=mtype,
        qty=qty,
        ref=(row.get("ref") or "").strip(),
        note=(row.get("note") or "").strip(),
    )


def load_movements(path: Path) -> List[Movement]:
    if not path.exists():
        raise DataError(f"missing {path.name} in {path.parent}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        movements = [parse_movement(row, i) for i, row in enumerate(reader, start=2)]
    movements.sort(key=lambda m: m.date)
    return movements


def load_purchase_orders(path: Path) -> List[PurchaseOrder]:
    if not path.exists():
        return []  # older data directories predate purchase orders
    orders = []
    for row in _read_json(path):
        try:
            status = POStatus(row.get("status", "open").lower())
        except ValueError:
            raise DataError(f"{row.get('id')}: unknown status {row.get('status')!r}") from None
        orders.append(
            PurchaseOrder(
                id=row["id"],
                supplier=row["supplier"],
                shop=row["shop"].strip().upper(),
                status=status,
                ordered=parse_date(row["ordered"], f"ordered on {row['id']}"),
                expected=_optional_date(row.get("expected"), f"expected on {row['id']}"),
                lines=[POLine(l["sku"].strip().upper(), float(l["qty"])) for l in row.get("lines", [])],
            )
        )
    return orders


def load(data_dir: Path) -> Inventory:
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise DataError(f"data directory not found: {data_dir}")
    return Inventory(
        shops=load_shops(data_dir / "shops.json"),
        items=load_items(data_dir / "items.json"),
        suppliers=load_suppliers(data_dir / "suppliers.json"),
        movements=load_movements(data_dir / "movements.csv"),
        purchase_orders=load_purchase_orders(data_dir / "purchase_orders.json"),
    )


def movement_row(m: Movement) -> Dict[str, str]:
    qty = int(m.qty) if float(m.qty).is_integer() else m.qty
    return {
        "date": m.date.isoformat(),
        "shop": m.shop,
        "sku": m.sku,
        "type": m.type.value,
        "qty": str(qty),
        "ref": m.ref,
        "note": m.note,
    }


def append_movements(path: Path, movements: Iterable[Movement]) -> int:
    path = Path(path)
    new_file = not path.exists()
    count = 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MOVEMENT_FIELDS)
        if new_file:
            writer.writeheader()
        for m in movements:
            writer.writerow(movement_row(m))
            count += 1
    return count
