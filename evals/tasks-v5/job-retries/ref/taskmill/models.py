"""Job records and the states a job moves through.

A job is one row in the ``jobs`` table. Its life is short:

    queued --(worker claims it)--> running --(handler returns)--> done
       ^                                   \\--(handler raises)--> queued again, later
       |                                    \\--(out of attempts / PermanentError)--> dead
       +--- (worker died: lease expired) ---+

``cancelled`` is set by hand from the CLI. Times are UNIX timestamps in
seconds (floats), taken from whatever ``Clock`` the caller uses.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


class Status(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"  # older jobs only; new failures retry, then go to DEAD
    DEAD = "dead"
    CANCELLED = "cancelled"

    def __str__(self) -> str:  # so f-strings print "done", not "Status.DONE"
        return self.value


#: States a job never leaves on its own.
TERMINAL = frozenset({Status.DONE, Status.FAILED, Status.DEAD, Status.CANCELLED})

#: States the CLI lets you requeue from.
REQUEUEABLE = frozenset({Status.FAILED, Status.DEAD, Status.CANCELLED})


@dataclass
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    run_at: float
    created_at: float
    updated_at: float
    started_at: float | None = None
    finished_at: float | None = None
    worker_id: str | None = None
    last_error: str | None = None
    priority: int = 0
    queue: str = "default"
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Job":
        data = dict(row)
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        payload = data.pop("payload", "{}")
        job = cls(
            payload=json.loads(payload) if isinstance(payload, str) else dict(payload or {}),
            **{k: data.pop(k) for k in list(data) if k in known},
        )
        job.extra = data
        return job

    @property
    def is_terminal(self) -> bool:
        return Status(self.status) in TERMINAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "queue": self.queue,
            "status": str(self.status),
            "priority": self.priority,
            "attempts": self.attempts,
            "run_at": self.run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "worker_id": self.worker_id,
            "last_error": self.last_error,
            "payload": self.payload,
        }

    def summary(self) -> str:
        err = f"  ({self.last_error.splitlines()[-1][:60]})" if self.last_error else ""
        return f"#{self.id:<6} {self.kind:<22} {str(self.status):<10} attempts={self.attempts}{err}"
