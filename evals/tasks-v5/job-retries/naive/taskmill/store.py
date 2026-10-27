"""SQLite-backed job store.

One file holds every job and its event history. The store knows nothing about
clocks: every method that writes a time takes ``now`` from its caller.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

from .errors import InvalidTransition, JobNotFound
from .models import REQUEUEABLE, Job, Status

# Each entry upgrades the schema by one version (PRAGMA user_version).
MIGRATIONS: list[str] = [
    # 1: the jobs table
    """
    CREATE TABLE jobs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        kind        TEXT    NOT NULL,
        payload     TEXT    NOT NULL DEFAULT '{}',
        status      TEXT    NOT NULL DEFAULT 'queued',
        attempts    INTEGER NOT NULL DEFAULT 0,
        run_at      REAL    NOT NULL,
        created_at  REAL    NOT NULL,
        updated_at  REAL    NOT NULL,
        started_at  REAL,
        finished_at REAL,
        worker_id   TEXT,
        last_error  TEXT
    );
    CREATE INDEX jobs_due ON jobs (status, run_at);
    """,
    # 2: priorities
    """
    ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;
    """,
    # 3: named queues
    """
    ALTER TABLE jobs ADD COLUMN queue TEXT NOT NULL DEFAULT 'default';
    CREATE INDEX jobs_queue ON jobs (queue, status);
    """,
    # 4: event history
    """
    CREATE TABLE job_events (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id  INTEGER NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
        at      REAL    NOT NULL,
        event   TEXT    NOT NULL,
        detail  TEXT
    );
    CREATE INDEX job_events_job ON job_events (job_id, id);
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)


class JobStore:
    """All reads and writes of jobs go through here.

    One ``JobStore`` wraps one sqlite3 connection, so give each thread or
    process its own instance.
    """

    def __init__(self, path: str | os.PathLike[str], *, timeout: float = 10.0):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=timeout)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    # -- lifecycle -------------------------------------------------------

    def migrate(self) -> int:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            self._conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        return SCHEMA_VERSION

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "JobStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- writes ----------------------------------------------------------

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        run_at: float | None = None,
        priority: int = 0,
        queue: str = "default",
        now: float | None = None,
    ) -> Job:
        """Add a job. It becomes due at ``run_at`` (default: ``now``)."""
        now = time.time() if now is None else now
        run_at = now if run_at is None else run_at
        cur = self._conn.execute(
            "INSERT INTO jobs (kind, payload, status, attempts, run_at, created_at, updated_at, priority, queue)"
            " VALUES (?, ?, 'queued', 0, ?, ?, ?, ?, ?)",
            (kind, json.dumps(payload or {}, sort_keys=True), run_at, now, now, priority, queue),
        )
        job_id = cur.lastrowid
        self._event(job_id, now, "enqueued", f"run_at={run_at}")
        self._conn.commit()
        return self.get_or_raise(job_id)

    def claim_next(self, now: float, worker_id: str, queues: Iterable[str] | None = None) -> Job | None:
        """Mark the next due job as running and return it, or None if nothing is due.

        Highest priority first, then oldest ``run_at``.
        """
        where, args = "status = 'queued' AND run_at <= ?", [now]
        if queues:
            queues = list(queues)
            where += f" AND queue IN ({', '.join('?' for _ in queues)})"
            args += queues
        row = self._conn.execute(
            f"SELECT id FROM jobs WHERE {where} ORDER BY priority DESC, run_at, id LIMIT 1", args
        ).fetchone()
        if row is None:
            return None
        # Only one worker process polls the queue, so a plain
        # select-then-update is enough here; no locking needed.
        self._conn.execute(
            "UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ?,"
            " worker_id = ?, updated_at = ? WHERE id = ?",
            (now, worker_id, now, row["id"]),
        )
        self._event(row["id"], now, "claimed", worker_id)
        self._conn.commit()
        return self.get(row["id"])

    def mark_done(self, job_id: int, now: float) -> None:
        self._finish(job_id, now, Status.DONE, None)

    def mark_failed(self, job_id: int, now: float, error: str) -> None:
        self._finish(job_id, now, Status.FAILED, error)

    def schedule_retry(self, job_id: int, now: float, run_at: float, error: str) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = 'queued', run_at = ?, updated_at = ?, last_error = ? WHERE id = ?",
            (run_at, now, error, job_id),
        )
        self._event(job_id, now, "retry", None)
        self._conn.commit()

    def _finish(self, job_id: int, now: float, status: Status, error: str | None) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?, last_error = ? WHERE id = ?",
            (status.value, now, now, error, job_id),
        )
        self._event(job_id, now, status.value, (error or "").splitlines()[-1][:200] if error else None)
        self._conn.commit()

    def requeue(self, job_id: int, now: float) -> Job:
        """Put a failed or cancelled job back in the queue, due now."""
        job = self.get_or_raise(job_id)
        if Status(job.status) not in REQUEUEABLE:
            raise InvalidTransition(f"job #{job_id} is {job.status}; only failed or cancelled jobs can be requeued")
        self._conn.execute(
            "UPDATE jobs SET status = 'queued', run_at = ?, updated_at = ?, finished_at = NULL,"
            " worker_id = NULL WHERE id = ?",
            (now, now, job_id),
        )
        self._event(job_id, now, "requeued", None)
        self._conn.commit()
        return self.get_or_raise(job_id)

    def cancel(self, job_id: int, now: float) -> Job:
        job = self.get_or_raise(job_id)
        if Status(job.status) is not Status.QUEUED:
            raise InvalidTransition(f"job #{job_id} is {job.status}; only queued jobs can be cancelled")
        self._conn.execute(
            "UPDATE jobs SET status = 'cancelled', updated_at = ?, finished_at = ? WHERE id = ?",
            (now, now, job_id),
        )
        self._event(job_id, now, "cancelled", None)
        self._conn.commit()
        return self.get_or_raise(job_id)

    def purge(self, before: float, statuses: Iterable[str] = ("done", "cancelled")) -> int:
        """Delete finished jobs (and their events) last touched before ``before``."""
        statuses = list(statuses)
        cur = self._conn.execute(
            f"DELETE FROM jobs WHERE status IN ({', '.join('?' for _ in statuses)}) AND updated_at < ?",
            (*statuses, before),
        )
        self._conn.commit()
        return cur.rowcount

    def _event(self, job_id: int, at: float, event: str, detail: str | None) -> None:
        self._conn.execute(
            "INSERT INTO job_events (job_id, at, event, detail) VALUES (?, ?, ?, ?)",
            (job_id, at, event, detail),
        )

    # -- reads -----------------------------------------------------------

    def get(self, job_id: int) -> Job | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job.from_row(row) if row else None

    def get_or_raise(self, job_id: int) -> Job:
        job = self.get(job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def list(
        self,
        status: str | None = None,
        kind: str | None = None,
        queue: str | None = None,
        limit: int = 100,
    ) -> list[Job]:
        clauses, args = [], []
        for col, val in (("status", status), ("kind", kind), ("queue", queue)):
            if val is not None:
                clauses.append(f"{col} = ?")
                args.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(f"SELECT * FROM jobs {where} ORDER BY id LIMIT ?", (*args, limit)).fetchall()
        return [Job.from_row(r) for r in rows]

    def iter_all(self, batch: int = 500) -> Iterator[Job]:
        last = 0
        while True:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE id > ? ORDER BY id LIMIT ?", (last, batch)
            ).fetchall()
            if not rows:
                return
            for r in rows:
                yield Job.from_row(r)
            last = rows[-1]["id"]

    def counts(self) -> dict[str, int]:
        """Number of jobs in each status (statuses with no jobs are 0)."""
        out = {s.value: 0 for s in Status}
        for row in self._conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"):
            out[row["status"]] = row["n"]
        return out

    def oldest_due(self, now: float) -> float | None:
        """run_at of the oldest queued job that is already due, if any."""
        row = self._conn.execute(
            "SELECT MIN(run_at) AS t FROM jobs WHERE status = 'queued' AND run_at <= ?", (now,)
        ).fetchone()
        return row["t"]

    def events(self, job_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT at, event, detail FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]
