"""Reorder suggestions: what each shop needs to order, and how much.

For every shop and item:

- daily usage = (sales + waste over the last 28 days) / 28. Transfers between
  shops and returns to the supplier are not usage, and neither are catering
  jobs (sales with "catering" in the note). A shop open for less than 28 days
  divides by the days it has been open.
- cover = stock on hand + quantity on OPEN purchase orders for that shop.
- days to delivery = from today to the first day the supplier delivers on,
  on or after today + lead time (suppliers only come on their delivery_days).
- reorder point = daily usage x (days to delivery + 3 days' safety stock).
- if cover is below the reorder point, order up to (days to delivery + 14 days)
  of usage, minus cover, rounded up to whole supplier cases.
- items from a supplier on hold are not ordered; they are returned separately
  so the CLI can show them in an "on hold" note.

The ledger is large (a year of three shops), so it is read in one pass.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from .ledger import window
from .models import Movement, MovementType, Shop, Supplier
from .store import Inventory

USAGE_DAYS = 28
SAFETY_DAYS = 3
MAX_COVER_DAYS = 14
USAGE_TYPES = frozenset((MovementType.SALE, MovementType.WASTE))

Key = Tuple[str, str]


@dataclass
class ReorderLine:
    shop: str
    sku: str
    name: str
    supplier: str
    daily_usage: float
    on_hand: float
    on_order: float
    days_to_delivery: int
    reorder_point: float
    case_size: int
    order_qty: int
    on_hold: bool = False

    def as_dict(self) -> dict:
        d = asdict(self)
        d["daily_usage"] = round(self.daily_usage, 2)
        d["reorder_point"] = round(self.reorder_point, 2)
        return d


def days_to_delivery(supplier: Supplier, today: date) -> int:
    """Days until an order placed today can arrive."""
    arrive = today + timedelta(days=supplier.lead_time_days)
    for _ in range(7):
        if supplier.delivers_on(arrive):
            break
        arrive += timedelta(days=1)
    return (arrive - today).days


def is_catering(m: Movement) -> bool:
    """One-off catering jobs: rung up as sales with "catering" in the note."""
    return m.type is MovementType.SALE and "catering" in m.note.lower()


def usage_days(shop: Optional[Shop], today: date) -> int:
    """Days to average usage over: 28, or fewer for a shop opened since."""
    if shop is not None and shop.opened is not None:
        open_days = (today - shop.opened).days + 1
        if open_days < USAGE_DAYS:
            return max(1, open_days)
    return USAGE_DAYS


def _scan(inv: Inventory, today: date) -> Tuple[Dict[Key, float], Dict[Key, float]]:
    """(on hand, usage over the window) per (shop, sku), in one pass."""
    since, _ = window(today, USAGE_DAYS)
    levels: Dict[Key, float] = defaultdict(float)
    used: Dict[Key, float] = defaultdict(float)
    for m in inv.movements:
        if m.date > today:
            continue
        key = (m.shop, m.sku)
        levels[key] += m.signed_qty
        if m.date >= since and m.type in USAGE_TYPES and not is_catering(m):
            used[key] += m.qty
    return levels, used


def _open_orders(inv: Inventory) -> Dict[Key, float]:
    coming: Dict[Key, float] = defaultdict(float)
    for po in inv.purchase_orders:
        if po.is_open():
            for line in po.lines:
                coming[(po.shop, line.sku)] += line.qty
    return coming


def suggest(inv: Inventory, today: date, shop: Optional[str] = None) -> List[ReorderLine]:
    """Every (shop, item) that needs ordering. Lines for suppliers on hold have
    on_hold=True and must not be ordered."""
    levels, used = _scan(inv, today)
    coming = _open_orders(inv)
    shops = [shop] if shop else inv.shop_codes()
    lines = []
    for s in shops:
        span = usage_days(inv.shops.get(s), today)
        for sku, item in sorted(inv.items.items()):
            supplier = inv.suppliers.get(item.supplier)
            if supplier is None:
                continue
            usage = used.get((s, sku), 0.0) / span
            if usage <= 0:
                continue
            have = levels.get((s, sku), 0.0)
            on_order = coming.get((s, sku), 0.0)
            cover = have + on_order
            wait = days_to_delivery(supplier, today)
            point = usage * (wait + SAFETY_DAYS)
            if cover >= point:
                continue
            target = usage * (wait + MAX_COVER_DAYS) - cover
            case = supplier.case_size(sku)
            qty = int(math.ceil(target / case - 1e-9)) * case
            if qty <= 0:
                continue
            lines.append(ReorderLine(s, sku, item.name, supplier.id, usage, have, on_order,
                                     wait, point, case, qty, supplier.on_hold))
    return lines
