"""Record types. All amounts are int minor units of the record's currency (see money.py)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Optional

ACTIVE = "active"
SUSPENDED = "suspended"

SUCCEEDED = "succeeded"
FAILED = "failed"
VOIDED = "voided"


class Record:
    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        names = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        return cls(**{k: v for k, v in data.items() if k in names})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[call-overload]


@dataclass
class Merchant(Record):
    id: str
    name: str
    fee_bps: int
    fee_fixed_cents: int
    created_at: str
    status: str = ACTIVE
    email: Optional[str] = None
    currency: str = "USD"

    @property
    def active(self) -> bool:
        return self.status == ACTIVE


@dataclass
class Charge(Record):
    id: str
    merchant_id: str
    amount_cents: int
    fee_cents: int
    description: str
    gateway_ref: str
    created_at: str
    status: str = SUCCEEDED
    currency: str = "USD"


@dataclass
class LedgerEntry(Record):
    id: str
    merchant_id: str
    kind: str
    amount_cents: int
    ref: str
    memo: str
    created_at: str


@dataclass
class Payout(Record):
    id: str
    merchant_id: str
    amount_cents: int
    gateway_ref: str
    created_at: str


@dataclass
class Refund(Record):
    id: str
    charge_id: str
    merchant_id: str
    amount_cents: int
    currency: str
    gateway_ref: str
    created_at: str
    reason: Optional[str] = None
