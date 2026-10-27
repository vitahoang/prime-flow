"""Purchase orders: listing, totals and what is still to come."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from .models import POStatus, PurchaseOrder, Supplier


def list_orders(orders: Iterable[PurchaseOrder], status: Optional[POStatus] = None,
                shop: Optional[str] = None, supplier: Optional[str] = None) -> List[PurchaseOrder]:
    shop = shop.upper() if shop else None
    out = []
    for po in orders:
        if status is not None and po.status is not status:
            continue
        if shop and po.shop != shop:
            continue
        if supplier and po.supplier != supplier:
            continue
        out.append(po)
    return sorted(out, key=lambda po: (po.ordered, po.id))


def order_value(po: PurchaseOrder, supplier: Optional[Supplier]) -> float:
    if supplier is None:
        return 0.0
    return round(sum(line.qty * supplier.unit_cost(line.sku) for line in po.lines), 2)


def overdue(orders: Iterable[PurchaseOrder], today: date) -> List[PurchaseOrder]:
    """Open orders whose expected date has passed."""
    return [po for po in orders
            if po.is_open() and po.expected is not None and po.expected < today]


def not_received(orders: Iterable[PurchaseOrder], sku: str,
                 shop: Optional[str] = None) -> float:
    """Quantity of ``sku`` ordered but not received yet."""
    sku = sku.upper()
    shop = shop.upper() if shop else None
    total = 0.0
    for po in orders:
        if po.status is POStatus.RECEIVED:
            continue
        if shop and po.shop != shop:
            continue
        total += po.qty_for(sku)
    return total


def counts_by_status(orders: Iterable[PurchaseOrder]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for po in orders:
        counts[po.status.value] += 1
    return dict(counts)


def lines_by_supplier(orders: Iterable[PurchaseOrder]) -> Dict[str, List[Tuple[str, str, float]]]:
    """supplier id -> [(po id, sku, qty)], for the weekly supplier email."""
    out: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
    for po in orders:
        for line in po.lines:
            out[po.supplier].append((po.id, line.sku, line.qty))
    return dict(out)


def next_po_id(orders: Iterable[PurchaseOrder]) -> str:
    highest = 0
    for po in orders:
        digits = po.id.rsplit("-", 1)[-1]
        if digits.isdigit():
            highest = max(highest, int(digits))
    return f"PO-{highest + 1:04d}"
