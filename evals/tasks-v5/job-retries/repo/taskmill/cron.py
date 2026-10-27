"""Periodic jobs: enqueue a job on a schedule.

Each entry fires every ``every`` seconds, aligned to the epoch, so restarts
don't drift. ``tick(now)`` enqueues whatever has come due since the last
tick. The schedule lives in memory; state is not persisted.

NOTE: superseded by the system crontab calling ``taskmill enqueue``; kept
until the reporting jobs are moved over.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from .store import JobStore

log = logging.getLogger("taskmill.cron")


@dataclass
class Entry:
    kind: str
    every: float
    payload: dict[str, Any] = field(default_factory=dict)
    queue: str = "default"
    last_slot: int | None = None

    def slot(self, now: float) -> int:
        return math.floor(now / self.every)


class Schedule:
    def __init__(self, store: JobStore):
        self.store = store
        self.entries: list[Entry] = []

    def every(self, seconds: float, kind: str, payload: dict[str, Any] | None = None,
              queue: str = "default") -> Entry:
        if seconds < 60:
            raise ValueError("cron entries must be at least a minute apart")
        entry = Entry(kind, seconds, payload or {}, queue)
        self.entries.append(entry)
        return entry

    def tick(self, now: float) -> int:
        fired = 0
        for entry in self.entries:
            slot = entry.slot(now)
            if entry.last_slot is None:
                entry.last_slot = slot  # don't fire on start-up
                continue
            if slot > entry.last_slot:
                self.store.enqueue(entry.kind, entry.payload, run_at=slot * entry.every,
                                   queue=entry.queue, now=now)
                entry.last_slot = slot
                fired += 1
                log.debug("cron fired %s", entry.kind)
        return fired
