"""Reorder suggestions: what each shop needs to order, and how much.

For every shop and item:

- daily usage = (sales + waste over the last 28 days) / 28. Transfers between
  shops and returns to the supplier are not usage.
- cover = stock on hand + quantity on OPEN purchase orders for that shop.
- reorder point = daily usage x (supplier lead time + 3 days' safety stock).
- if cover is below the reorder point, order up to (lead time + 14 days) of
  usage, minus cover, rounded up to whole supplier cases.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import List, Optional

from .ledger import filter_movements, on_hand_by_shop, window
from .models import MovementType
from .store import Inventory

USAGE_DAYS = 28
SAFETY_DAYS = 3
MAX_COVER_DAYS = 14
USAGE_TYPES = (MovementType.SALE, MovementType.WASTE)


@dataclass
class ReorderLine:
    shop: str
    sku: str
    name: str
    supplier: str
    daily_usage: float
    on_hand: float
    on_order: float
    reorder_point: float
    case_size: int
    order_qty: int

    def as_dict(self) -> dict:
        d = asdict(self)
        d["daily_usage"] = round(self.daily_usage, 2)
        d["reorder_point"] = round(self.reorder_point, 2)
        return d


def daily_usage(inv: Inventory, shop: str, sku: str, today: date) -> float:
    since, until = window(today, USAGE_DAYS)
    used = filter_movements(inv.movements, shop=shop, sku=sku, since=since, until=until,
                            types=USAGE_TYPES)
    return sum(m.qty for m in used) / USAGE_DAYS


def on_order(inv: Inventory, shop: str, sku: str) -> float:
    return sum(po.qty_for(sku) for po in inv.purchase_orders if po.is_open() and po.shop == shop)


def suggest(inv: Inventory, today: date, shop: Optional[str] = None) -> List[ReorderLine]:
    levels = on_hand_by_shop(inv.movements, as_of=today)
    shops = [shop] if shop else inv.shop_codes()
    lines = []
    for s in shops:
        for sku, item in sorted(inv.items.items()):
            supplier = inv.suppliers.get(item.supplier)
            if supplier is None:
                continue
            usage = daily_usage(inv, s, sku, today)
            if usage <= 0:
                continue
            have = levels.get((s, sku), 0.0)
            coming = on_order(inv, s, sku)
            cover = have + coming
            point = usage * (supplier.lead_time_days + SAFETY_DAYS)
            if cover >= point:
                continue
            target = usage * (supplier.lead_time_days + MAX_COVER_DAYS) - cover
            case = supplier.case_size(sku)
            qty = int(math.ceil(target / case - 1e-9)) * case
            if qty <= 0:
                continue
            lines.append(ReorderLine(s, sku, item.name, supplier.id, usage, have, coming,
                                     point, case, qty))
    return lines
