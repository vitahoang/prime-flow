"""Plain data objects. Loading and saving lives in store.py."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from . import money


@dataclass
class Customer:
    id: str
    name: str
    email: str
    timezone: str  # IANA name, e.g. "Asia/Singapore"
    currency: str = "GBP"
    address: tuple[str, ...] = ()
    contact: str = ""

    def __post_init__(self):
        self.address = tuple(self.address)


@dataclass
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal

    @property
    def amount(self) -> Decimal:
        return money.round_money(self.quantity * self.unit_price)


@dataclass
class Invoice:
    id: str
    customer_id: str
    # When the invoice was issued. New records carry an aware UTC datetime
    # (from "issued_at"); records from the old v0 data file only have a date
    # (from "issued_on").
    issued: datetime | date
    terms_days: int
    currency: str
    lines: list[LineItem] = field(default_factory=list)
    tax_rate: Decimal = Decimal("0")
    notes: str = ""
    void: bool = False
    po_number: str = ""

    @property
    def is_legacy(self) -> bool:
        return not isinstance(self.issued, datetime)

    @property
    def subtotal(self) -> Decimal:
        return money.round_money(sum((line.amount for line in self.lines), Decimal("0")))

    @property
    def tax(self) -> Decimal:
        return money.round_money(self.subtotal * self.tax_rate)

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax


@dataclass
class Fee:
    """A late fee charged on an invoice (written by the `overdue` run)."""

    invoice_id: str
    amount: Decimal
    charged_at: datetime
    note: str = ""


@dataclass
class Payment:
    invoice_id: str
    amount: Decimal
    paid_at: datetime
    method: str = "bank transfer"
    reference: str = ""
