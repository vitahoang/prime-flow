"""Data model. Every record round-trips through a plain dict (the JSON files)."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from .money import ZERO, check_currency, parse_amount


def parse_ts(value) -> datetime:
    """Parse an ISO timestamp. Naive timestamps are taken as UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Tier:
    """One row of a plan's price table.

    ``up_to`` is the last unit (inclusive) the row covers; None means "and
    above". ``unit_price`` is in major units of the plan's currency.
    """

    up_to: Optional[int]
    unit_price: Decimal

    @classmethod
    def from_dict(cls, d):
        up_to = d.get("up_to")
        return cls(up_to=None if up_to is None else int(up_to), unit_price=parse_amount(d["unit_price"]))

    def to_dict(self):
        return {"up_to": self.up_to, "unit_price": str(self.unit_price)}


@dataclass
class Plan:
    id: str
    name: str
    currency: str
    base_fee: Decimal
    tiers: List[Tier]
    free_units: int = 0
    minimum_charge: Decimal = ZERO
    active: bool = True

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            currency=check_currency(d.get("currency", "USD")),
            base_fee=parse_amount(d.get("base_fee", "0")),
            tiers=[Tier.from_dict(t) for t in d.get("tiers", [])],
            free_units=int(d.get("free_units", 0)),
            minimum_charge=parse_amount(d.get("minimum_charge", "0")),
            active=bool(d.get("active", True)),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "currency": self.currency,
            "base_fee": str(self.base_fee),
            "tiers": [t.to_dict() for t in self.tiers],
            "free_units": self.free_units,
            "minimum_charge": str(self.minimum_charge),
            "active": self.active,
        }


@dataclass
class Customer:
    id: str
    name: str
    email: str
    country: str
    currency: str
    timezone: str
    plan_id: str
    credit_balance: Decimal = ZERO  # major units, customer's currency
    created_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)  # free-form labels for support

    @classmethod
    def from_dict(cls, d):
        created = d.get("created_at")
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            email=d.get("email", ""),
            country=(d.get("country") or "").upper(),
            currency=check_currency(d.get("currency", "USD")),
            timezone=d.get("timezone") or "UTC",
            plan_id=d["plan_id"],
            credit_balance=parse_amount(d.get("credit_balance", "0")),
            created_at=parse_ts(created) if created else None,
            tags=[str(x) for x in d.get("tags", [])],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "country": self.country,
            "currency": self.currency,
            "timezone": self.timezone,
            "plan_id": self.plan_id,
            "credit_balance": str(self.credit_balance),
            "created_at": format_ts(self.created_at) if self.created_at else None,
            "tags": list(self.tags),
        }


@dataclass
class Subscription:
    """A customer was on ``plan_id`` from ``started_at`` until the next record."""

    customer_id: str
    plan_id: str
    started_at: datetime

    @classmethod
    def from_dict(cls, d):
        return cls(customer_id=d["customer_id"], plan_id=d["plan_id"], started_at=parse_ts(d["started_at"]))

    def to_dict(self):
        return {"customer_id": self.customer_id, "plan_id": self.plan_id, "started_at": format_ts(self.started_at)}


@dataclass
class UsageEvent:
    """One usage record as it arrived from an SDK.

    ``timestamp`` is when the usage happened (client clock); ``received_at`` is
    when our ingest endpoint stored it. ``units`` is how much usage the event
    carries: 1 for a single call, N for a batch the SDK buffered.
    """

    event_id: str
    customer_id: str
    timestamp: datetime
    received_at: datetime
    units: int = 1
    metric: str = "api_calls"
    source: str = "sdk"

    @classmethod
    def from_dict(cls, d):
        ts = parse_ts(d["timestamp"])
        return cls(
            event_id=d["event_id"],
            customer_id=d["customer_id"],
            timestamp=ts,
            received_at=parse_ts(d["received_at"]) if d.get("received_at") else ts,
            units=int(d.get("units", 1)),
            metric=d.get("metric", "api_calls"),
            source=d.get("source", "sdk"),
        )

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "customer_id": self.customer_id,
            "timestamp": format_ts(self.timestamp),
            "received_at": format_ts(self.received_at),
            "units": self.units,
            "metric": self.metric,
            "source": self.source,
        }


# Invoice model: sketched when we started on invoicing, not used anywhere yet.


@dataclass
class InvoiceLine:
    description: str
    amount: Decimal = ZERO  # major units


@dataclass
class Invoice:
    customer_id: str
    period_start: date
    period_end: date
    currency: str
    lines: List[InvoiceLine] = field(default_factory=list)
    status: str = "draft"
    notes: str = ""

    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)
