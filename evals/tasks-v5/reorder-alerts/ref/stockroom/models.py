"""Core records: shops, items, suppliers, stock movements and purchase orders.

Everything here is a plain dataclass. Loading and saving lives in
``stockroom.store``; stock arithmetic lives in ``stockroom.ledger``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Weekday names as written in suppliers.json, Monday first (date.weekday() order).
WEEKDAYS: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class MovementType(str, Enum):
    """What happened to the stock. ``qty`` on a Movement is always positive;
    the type decides which way it goes."""

    SALE = "sale"                  # sold over the counter (POS export)
    DELIVERY = "delivery"          # arrived from a supplier
    WASTE = "waste"                # binned: out of date, dropped, burnt
    TRANSFER_IN = "transfer_in"    # moved here from another of our shops
    TRANSFER_OUT = "transfer_out"  # moved from here to another of our shops
    RETURN = "return"              # sent back to the supplier (damaged, wrong item)

    @property
    def sign(self) -> int:
        return 1 if self in (MovementType.DELIVERY, MovementType.TRANSFER_IN) else -1

    @property
    def is_inbound(self) -> bool:
        return self.sign > 0


INBOUND = frozenset(t for t in MovementType if t.is_inbound)
OUTBOUND = frozenset(t for t in MovementType if not t.is_inbound)


class POStatus(str, Enum):
    OPEN = "open"            # sent to the supplier, not delivered yet
    RECEIVED = "received"    # delivered; the delivery is in movements.csv
    CANCELLED = "cancelled"  # will not arrive


@dataclass(frozen=True)
class Shop:
    code: str
    name: str
    opened: Optional[date] = None

    def label(self) -> str:
        return f"{self.name} ({self.code})"


@dataclass
class Item:
    sku: str
    name: str
    unit: str
    supplier: str
    category: str = "other"
    # min_stock: reorder threshold, chain-wide, used by the reorder warnings
    # (see README). 0 means "never warn".
    min_stock: int = 0

    def __post_init__(self) -> None:
        self.sku = self.sku.strip().upper()
        if self.min_stock < 0:
            raise ValueError(f"{self.sku}: min_stock cannot be negative")


@dataclass
class SupplierItem:
    """What a supplier sells us for one SKU, and in what pack."""

    sku: str
    case_size: int = 1
    unit_cost: float = 0.0

    def __post_init__(self) -> None:
        self.sku = self.sku.strip().upper()
        if self.case_size < 1:
            raise ValueError(f"{self.sku}: case_size must be at least 1")


@dataclass
class Supplier:
    id: str
    name: str
    lead_time_days: int = 1
    contact: str = ""
    items: Dict[str, SupplierItem] = field(default_factory=dict)
    # Days of the week the supplier's van comes, e.g. ("tue", "fri").
    delivery_days: Tuple[str, ...] = WEEKDAYS
    # Marco puts a supplier on hold during a billing dispute: no new orders.
    on_hold: bool = False

    def __post_init__(self) -> None:
        self.delivery_days = tuple(d.strip().lower()[:3] for d in self.delivery_days)
        unknown = [d for d in self.delivery_days if d not in WEEKDAYS]
        if unknown:
            raise ValueError(f"{self.id}: unknown delivery day(s) {', '.join(unknown)}")

    def delivers_on(self, day: date) -> bool:
        return WEEKDAYS[day.weekday()] in self.delivery_days

    def case_size(self, sku: str) -> int:
        entry = self.items.get(sku.upper())
        return entry.case_size if entry else 1

    def unit_cost(self, sku: str) -> float:
        entry = self.items.get(sku.upper())
        return entry.unit_cost if entry else 0.0

    def sells(self, sku: str) -> bool:
        return sku.upper() in self.items


@dataclass(frozen=True)
class Movement:
    date: date
    shop: str
    sku: str
    type: MovementType
    qty: float
    ref: str = ""
    note: str = ""

    @property
    def signed_qty(self) -> float:
        return self.qty * self.type.sign


@dataclass(frozen=True)
class POLine:
    sku: str
    qty: float


@dataclass
class PurchaseOrder:
    id: str
    supplier: str
    shop: str
    status: POStatus
    ordered: date
    expected: Optional[date] = None
    lines: List[POLine] = field(default_factory=list)

    def qty_for(self, sku: str) -> float:
        sku = sku.upper()
        return sum(line.qty for line in self.lines if line.sku == sku)

    @property
    def skus(self) -> List[str]:
        return sorted({line.sku for line in self.lines})

    def is_open(self) -> bool:
        return self.status is POStatus.OPEN
