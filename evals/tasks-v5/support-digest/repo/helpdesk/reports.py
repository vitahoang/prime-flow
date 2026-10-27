"""Backlog numbers for the team lead's dashboard."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from . import sla
from .models import ACTIVE_STATUSES, RESOLVED, STATUSES, Ticket
from .timeutil import ensure_aware


@dataclass(frozen=True)
class Backlog:
    by_status: dict
    by_assignee: dict
    breached: int
    at_risk: int
    unassigned: int


def backlog(tickets: Iterable[Ticket], now: datetime) -> Backlog:
    tickets = list(tickets)
    active = [t for t in tickets if t.status in ACTIVE_STATUSES]
    return Backlog(
        by_status={s: sum(1 for t in tickets if t.status == s) for s in STATUSES},
        by_assignee=dict(Counter(t.assignee for t in active if t.assignee)),
        breached=sum(1 for t in active if sla.is_breached(t, now)),
        at_risk=sum(1 for t in active if sla.is_at_risk(t, now)),
        unassigned=sum(1 for t in active if t.assignee is None),
    )


def resolved_between(tickets: Iterable[Ticket], start: datetime, end: datetime) -> list[Ticket]:
    start, end = ensure_aware(start), ensure_aware(end)
    return [
        t for t in tickets
        if t.status == RESOLVED and t.resolved_at is not None and start <= t.resolved_at < end
    ]


def median_resolution_hours(tickets: Iterable[Ticket]) -> float:
    hours = sorted(
        (t.resolved_at - t.created_at) / timedelta(hours=1)
        for t in tickets if t.resolved_at is not None
    )
    if not hours:
        return 0.0
    mid = len(hours) // 2
    return hours[mid] if len(hours) % 2 else (hours[mid - 1] + hours[mid]) / 2


def legacy_weekly_summary(tickets: Iterable[Ticket], week_start: datetime) -> str:
    # Used by the old Monday email, which was switched off. Kept until the
    # dashboard has a weekly view.
    week_end = ensure_aware(week_start) + timedelta(days=7)
    done = resolved_between(tickets, week_start, week_end)
    return f"{len(done)} tickets resolved in the week of {week_start:%d %b}"
