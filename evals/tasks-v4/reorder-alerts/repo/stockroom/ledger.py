"""Stock arithmetic over the movement log.

Stock on hand is never stored: it is the sum of every movement for a shop and
SKU (deliveries and transfers in add, everything else subtracts).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .models import Movement, MovementType, OUTBOUND

Key = Tuple[str, str]  # (shop, sku)


def filter_movements(
    movements: Iterable[Movement],
    shop: Optional[str] = None,
    sku: Optional[str] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
    types: Optional[Sequence[MovementType]] = None,
) -> List[Movement]:
    """Movements matching every filter given. ``since`` and ``until`` are inclusive."""
    shop = shop.upper() if shop else None
    sku = sku.upper() if sku else None
    wanted = set(types) if types else None
    out = []
    for m in movements:
        if shop and m.shop != shop:
            continue
        if sku and m.sku != sku:
            continue
        if since and m.date < since:
            continue
        if until and m.date > until:
            continue
        if wanted is not None and m.type not in wanted:
            continue
        out.append(m)
    return out


def on_hand_by_shop(movements: Iterable[Movement], as_of: Optional[date] = None) -> Dict[Key, float]:
    """Stock on hand for every (shop, sku) that has ever moved."""
    totals: Dict[Key, float] = defaultdict(float)
    for m in movements:
        if as_of and m.date > as_of:
            continue
        totals[(m.shop, m.sku)] += m.signed_qty
    return dict(totals)


def on_hand(movements: Iterable[Movement], sku: str, shop: Optional[str] = None,
            as_of: Optional[date] = None) -> float:
    """Stock on hand for one SKU, in one shop or (shop=None) across the chain."""
    sku = sku.upper()
    shop = shop.upper() if shop else None
    total = 0.0
    for (s, k), qty in on_hand_by_shop(movements, as_of).items():
        if k == sku and (shop is None or s == shop):
            total += qty
    return total


def chain_totals(levels: Dict[Key, float]) -> Dict[str, float]:
    """Collapse per-shop levels into one figure per SKU."""
    totals: Dict[str, float] = defaultdict(float)
    for (_, sku), qty in levels.items():
        totals[sku] += qty
    return dict(totals)


def outflow_by_sku(movements: Iterable[Movement], since: date,
                   shop: Optional[str] = None) -> Dict[str, float]:
    """How much of each item is being used up since ``since``.

    Shown as the "out" column of ``stock --activity``.
    """
    totals: Dict[str, float] = defaultdict(float)
    for m in filter_movements(movements, shop=shop, since=since, types=sorted(OUTBOUND)):
        totals[m.sku] += m.qty
    return dict(totals)


def last_movement(movements: Iterable[Movement], sku: str, shop: str,
                  mtype: MovementType) -> Optional[Movement]:
    found = None
    for m in filter_movements(movements, shop=shop, sku=sku, types=[mtype]):
        if found is None or m.date >= found.date:
            found = m
    return found


def window(today: date, days: int) -> Tuple[date, date]:
    """The ``days`` calendar days ending today, inclusive of today."""
    if days < 1:
        raise ValueError("days must be at least 1")
    return today - timedelta(days=days - 1), today


def negative_stock(levels: Dict[Key, float]) -> List[Key]:
    """(shop, sku) pairs whose stock has gone below zero: usually a missed delivery
    or a transfer recorded at one end only."""
    return sorted(k for k, qty in levels.items() if qty < -1e-9)
