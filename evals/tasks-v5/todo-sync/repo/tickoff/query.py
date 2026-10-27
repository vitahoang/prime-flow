"""Read-only views over a replica: overdue, due soon, search, counts."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta


def open_tasks(replica, list_name: str | None = None):
    names = [list_name] if list_name else replica.lists()
    return [t for name in names for t in replica.list_tasks(name, include_done=False)]


def overdue(replica, today: date):
    iso = today.isoformat()
    return sorted((t for t in open_tasks(replica) if t.is_overdue(iso)), key=lambda t: (t.due, t.title))


def due_within(replica, today: date, days: int):
    start, end = today.isoformat(), (today + timedelta(days=days)).isoformat()
    found = [t for t in open_tasks(replica) if t.due and start <= t.due <= end]
    return sorted(found, key=lambda t: (t.due, t.list, t.order))


def search(replica, text: str, *, include_done: bool = False):
    words = text.lower().split()
    found = []
    for name in replica.lists():
        for task in replica.list_tasks(name, include_done=include_done):
            title = task.title.lower()
            if all(w in title for w in words):
                found.append(task)
    return found


def counts(replica) -> dict:
    """Open and done counts per list."""
    open_c, done_c = Counter(), Counter()
    for task in replica.tasks.values():
        (done_c if task.done else open_c)[task.list] += 1
    return {name: {"open": open_c[name], "done": done_c[name]} for name in replica.lists()}


def agenda(replica, today: date, days: int = 7) -> list[tuple[str, list]]:
    """Overdue first, then each of the next `days` days that has something due."""
    out = []
    late = overdue(replica, today)
    if late:
        out.append(("overdue", late))
    by_day: dict[str, list] = {}
    for task in due_within(replica, today, days):
        by_day.setdefault(task.due, []).append(task)
    out.extend(sorted(by_day.items()))
    return out
