"""Plain records for what lives in the database.

Amounts are integer cents (pence, for GBP) everywhere. Money coming in is
positive and money going out is negative: a salary is +250000, a coffee is
-450. Reports and budgets rely on that sign.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

CATEGORY_KINDS = ("expense", "income", "transfer")
RULE_MATCHES = ("contains", "startswith", "exact", "regex")
RULE_SIGNS = ("in", "out")


@dataclass
class Account:
    id: int
    name: str
    bank: str
    currency: str
    opened: Optional[date] = None
    closed: Optional[date] = None

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            bank=row["bank"],
            currency=row["currency"],
            opened=date.fromisoformat(row["opened"]) if row["opened"] else None,
            closed=date.fromisoformat(row["closed"]) if row["closed"] else None,
        )

    @property
    def is_open(self):
        return self.closed is None


@dataclass
class Category:
    id: int
    name: str
    kind: str = "expense"
    parent_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        return cls(id=row["id"], name=row["name"], kind=row["kind"], parent_id=row["parent_id"])


@dataclass
class Transaction:
    id: Optional[int]
    account_id: int
    posted: date
    amount_cents: int
    description: str
    category_id: Optional[int] = None
    note: Optional[str] = None
    source: str = "manual"

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            posted=date.fromisoformat(row["posted"]),
            amount_cents=row["amount_cents"],
            description=row["description"],
            category_id=row["category_id"],
            note=row["note"],
            source=row["source"],
        )

    @property
    def is_income(self):
        return self.amount_cents > 0


@dataclass
class Rule:
    id: Optional[int]
    pattern: str
    category_id: int
    match: str = "contains"
    priority: int = 100
    account_id: Optional[int] = None
    sign: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            pattern=row["pattern"],
            category_id=row["category_id"],
            match=row["match"],
            priority=row["priority"],
            account_id=row["account_id"],
            sign=row["sign"],
        )


@dataclass
class Budget:
    category_id: int
    amount_cents: int
