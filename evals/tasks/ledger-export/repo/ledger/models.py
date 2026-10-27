"""The ledger entry model."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(value: str) -> datetime:
    """Parse a stored UTC timestamp like ``2026-03-01T14:05:00Z``."""
    return datetime.strptime(value, TS_FORMAT).replace(tzinfo=timezone.utc)


def format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(TS_FORMAT)


@dataclass
class Entry:
    id: int
    ts: str  # UTC, TS_FORMAT
    description: str
    amount_cents: int  # positive = income, negative = expense
    category: str = "uncategorized"
    archived: bool = False

    @property
    def when(self) -> datetime:
        return parse_ts(self.ts)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        return cls(
            id=int(data["id"]),
            ts=data["ts"],
            description=data["description"],
            amount_cents=int(data["amount_cents"]),
            category=data.get("category", "uncategorized"),
            archived=bool(data.get("archived", False)),
        )
