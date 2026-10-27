"""Audit trail: who did what, when.

Events are appended to ``store.events`` and saved with the store. Nothing
reads them back except the CLI's ``log`` command and the tests.
"""

from __future__ import annotations

from typing import Optional

from . import clock
from .models import Event


def record(store, actor_id: Optional[str], action: str, resource_id: str, **detail) -> Event:
    event = Event(clock.now_iso(), actor_id, action, resource_id, dict(detail))
    store.events.append(event)
    return event


def recent(store, limit: int = 20, resource_id: Optional[str] = None) -> list[Event]:
    events = store.events
    if resource_id is not None:
        events = [e for e in events if e.resource_id == resource_id]
    return list(events[-limit:])


def by_actor(store, actor_id: str) -> list[Event]:
    return [e for e in store.events if e.actor_id == actor_id]


def format_event(event: Event) -> str:
    who = event.actor_id or "system"
    extra = " ".join(f"{k}={v}" for k, v in sorted(event.detail.items()))
    return f"{event.at}  {who:<9} {event.action:<18} {event.resource_id} {extra}".rstrip()
