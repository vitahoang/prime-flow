"""Weekly reports the owner asks for: waste and best sellers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from .ledger import filter_movements
from .models import MovementType
from .store import Inventory


@dataclass
class WasteLine:
    shop: str
    sku: str
    qty: float
    cost: float
    share_of_sales: Optional[float]  # waste / sales over the same period, None if no sales


def waste_report(inv: Inventory, since: date, until: date,
                 shop: Optional[str] = None) -> List[WasteLine]:
    waste: Dict[tuple, float] = defaultdict(float)
    sales: Dict[tuple, float] = defaultdict(float)
    for m in filter_movements(inv.movements, shop=shop, since=since, until=until,
                              types=[MovementType.WASTE, MovementType.SALE]):
        bucket = waste if m.type is MovementType.WASTE else sales
        bucket[(m.shop, m.sku)] += m.qty
    lines = []
    for (s, sku), qty in waste.items():
        supplier = inv.suppliers.get(inv.items[sku].supplier) if sku in inv.items else None
        cost = qty * supplier.unit_cost(sku) if supplier else 0.0
        sold = sales.get((s, sku), 0.0)
        lines.append(WasteLine(s, sku, qty, round(cost, 2), qty / sold if sold else None))
    lines.sort(key=lambda l: (-l.cost, l.shop, l.sku))
    return lines


def top_sellers(inv: Inventory, since: date, until: date, shop: Optional[str] = None,
                limit: int = 5) -> List[tuple]:
    """[(sku, qty sold)] best first."""
    sold: Dict[str, float] = defaultdict(float)
    for m in filter_movements(inv.movements, shop=shop, since=since, until=until,
                              types=[MovementType.SALE]):
        sold[m.sku] += m.qty
    ranked = sorted(sold.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]
