"""Filtering tickets for the agent views and reports."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Optional

from .models import PRIORITIES, Ticket

Predicate = Callable[[Ticket], bool]


@dataclass
class Query:
    """A simple ticket query; every field that is set must match."""

    assignee: Optional[str] = None
    statuses: Optional[set[str]] = None
    priorities: Optional[set[str]] = None
    tag: Optional[str] = None
    queue: Optional[str] = None
    text: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    unassigned_only: bool = False
    extra: list[Predicate] = field(default_factory=list)

    def matches(self, t: Ticket) -> bool:
        if self.unassigned_only and t.assignee is not None:
            return False
        if self.assignee is not None and t.assignee != self.assignee:
            return False
        if self.statuses is not None and t.status not in self.statuses:
            return False
        if self.priorities is not None and t.priority not in self.priorities:
            return False
        if self.tag is not None and self.tag not in t.tags:
            return False
        if self.queue is not None and t.queue != self.queue:
            return False
        if self.text is not None and self.text.lower() not in t.subject.lower():
            return False
        if self.created_after is not None and t.created_at < self.created_after:
            return False
        if self.created_before is not None and t.created_at >= self.created_before:
            return False
        if self.updated_before is not None and t.updated_at >= self.updated_before:
            return False
        return all(p(t) for p in self.extra)


def run(query: Query, tickets: Iterable[Ticket]) -> list[Ticket]:
    return [t for t in tickets if query.matches(t)]


def by_priority(tickets: Iterable[Ticket]) -> list[Ticket]:
    """Most urgent first, then oldest first."""
    rank = {p: i for i, p in enumerate(PRIORITIES)}
    return sorted(tickets, key=lambda t: (rank[t.priority], t.created_at, t.id))


def parse(text: str) -> Query:
    """Parse the agent-view search box, e.g. ``"assignee:mai status:open refund"``."""
    q = Query()
    words = []
    for token in text.split():
        name, sep, value = token.partition(":")
        if not sep:
            words.append(token)
        elif name == "assignee":
            q.assignee = value
        elif name == "status":
            q.statuses = set(value.split(","))
        elif name == "priority":
            q.priorities = set(value.split(","))
        elif name == "tag":
            q.tag = value
        elif name == "queue":
            q.queue = value
        elif name == "is" and value == "unassigned":
            q.unassigned_only = True
        else:
            words.append(token)
    if words:
        q.text = " ".join(words)
    return q
