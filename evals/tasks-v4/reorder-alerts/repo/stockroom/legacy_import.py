"""One-off import from the old "stock sheet" spreadsheet (2021-2023).

The sheet had one tab per shop with columns: Item, Code, Unit, Count, Min level,
Supplier. We imported it once when stockroom started; it is kept in case the
Harbour archive turns up. Not wired into the CLI.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from .models import Item, Movement, MovementType
from .units import convert, is_volume, is_weight

COLUMN_MAP = {
    "Item": "name",
    "Code": "sku",
    "Unit": "unit",
    "Count": "count",
    "Min level": "min_stock",
    "Supplier": "supplier",
}


def _normalise_unit(unit: str, count: float) -> Tuple[str, float]:
    """The sheet mixed grams and kg, ml and litres; keep kg and litres."""
    u = unit.strip().lower()
    if is_weight(u) and u != "kg":
        return "kg", convert(count, u, "kg")
    if is_volume(u) and u != "l":
        return "l", convert(count, u, "l")
    return unit.strip() or "each", count


def read_sheet(path: Path, shop: str, as_of: date) -> Tuple[Dict[str, Item], List[Movement]]:
    """Items from the sheet, plus one opening delivery per counted item."""
    items: Dict[str, Item] = {}
    openings: List[Movement] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        for raw in csv.DictReader(fh):
            row = {COLUMN_MAP[k]: (v or "").strip() for k, v in raw.items() if k in COLUMN_MAP}
            if not row.get("sku"):
                continue
            count = float(row.get("count") or 0)
            unit, count = _normalise_unit(row.get("unit", ""), count)
            item = Item(
                sku=row["sku"],
                name=row.get("name") or row["sku"],
                unit=unit,
                supplier=row.get("supplier", "").lower().replace(" ", "-"),
                min_stock=int(float(row.get("min_stock") or 0)),
            )
            items[item.sku] = item
            if count > 0:
                openings.append(Movement(as_of, shop.upper(), item.sku, MovementType.DELIVERY,
                                         count, ref="opening", note="legacy stock sheet"))
    return items, openings
