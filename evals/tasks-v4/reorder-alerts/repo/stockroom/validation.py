"""Sanity checks on a loaded Inventory, for ``python -m stockroom check``."""

from __future__ import annotations

from typing import List

from .ledger import negative_stock, on_hand_by_shop
from .models import MovementType, POStatus
from .store import Inventory


def check(inv: Inventory) -> List[str]:
    problems: List[str] = []

    for item in inv.items.values():
        supplier = inv.suppliers.get(item.supplier)
        if supplier is None:
            problems.append(f"{item.sku}: supplier {item.supplier!r} not in suppliers.json")
        elif not supplier.sells(item.sku):
            problems.append(f"{item.sku}: {supplier.id} has no case size/price for it")

    for supplier in inv.suppliers.values():
        if supplier.lead_time_days < 0:
            problems.append(f"{supplier.id}: negative lead time")
        for sku in supplier.items:
            if sku not in inv.items:
                problems.append(f"{supplier.id}: sells unknown SKU {sku}")

    for m in inv.movements:
        if m.shop not in inv.shops:
            problems.append(f"{m.date} {m.sku}: unknown shop {m.shop}")
        if m.sku not in inv.items:
            problems.append(f"{m.date} {m.shop}: unknown SKU {m.sku}")

    problems.extend(_unmatched_transfers(inv))

    for shop, sku in negative_stock(on_hand_by_shop(inv.movements)):
        problems.append(f"{shop} {sku}: stock below zero")

    seen = set()
    for po in inv.purchase_orders:
        if po.id in seen:
            problems.append(f"{po.id}: duplicate purchase order id")
        seen.add(po.id)
        if po.shop not in inv.shops:
            problems.append(f"{po.id}: unknown shop {po.shop}")
        if po.supplier not in inv.suppliers:
            problems.append(f"{po.id}: unknown supplier {po.supplier}")
        if po.status is POStatus.OPEN and not po.lines:
            problems.append(f"{po.id}: open order with no lines")
    return problems


def _unmatched_transfers(inv: Inventory) -> List[str]:
    """Every transfer_out should have a transfer_in with the same ref."""
    outs, ins = {}, {}
    for m in inv.movements:
        if m.type is MovementType.TRANSFER_OUT:
            outs[(m.ref, m.sku)] = m
        elif m.type is MovementType.TRANSFER_IN:
            ins[(m.ref, m.sku)] = m
    problems = []
    for key, m in sorted(outs.items(), key=lambda kv: kv[1].date):
        other = ins.get(key)
        if other is None:
            problems.append(f"transfer {m.ref or '(no ref)'} {m.sku}: sent from {m.shop} but never received")
        elif other.qty != m.qty:
            problems.append(f"transfer {m.ref} {m.sku}: sent {m.qty:g}, received {other.qty:g}")
    for key, m in ins.items():
        if key not in outs:
            problems.append(f"transfer {m.ref or '(no ref)'} {m.sku}: received at {m.shop} but never sent")
    return problems
