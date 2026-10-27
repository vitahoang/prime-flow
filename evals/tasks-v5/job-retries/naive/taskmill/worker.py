"""The worker loop: claim a due job, run its handler, record the outcome."""

from __future__ import annotations

import itertools
import logging
import os
import socket
import threading
from typing import Iterable

from .clock import Clock, SystemClock
from .errors import UnknownJobKind
from .metrics import Metrics
from .models import Job
from .registry import Registry
from .serialize import format_error
from .store import JobStore

log = logging.getLogger("taskmill.worker")

_seq = itertools.count(1)

MAX_ATTEMPTS = 3
RETRY_DELAY = 60.0  # doubled after each failed attempt


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{next(_seq)}"


class Worker:
    def __init__(
        self,
        store: JobStore,
        registry: Registry,
        clock: Clock | None = None,
        *,
        worker_id: str | None = None,
        queues: Iterable[str] | None = None,
        poll_interval: float = 1.0,
        metrics: Metrics | None = None,
    ):
        self.store = store
        self.registry = registry
        self.clock = clock or SystemClock()
        self.worker_id = worker_id or default_worker_id()
        self.queues = list(queues) if queues else None
        self.poll_interval = poll_interval
        self.metrics = metrics or Metrics()
        self._stop = threading.Event()

    def run_once(self) -> bool:
        """Run at most one due job. Returns True if a job was run."""
        job = self.store.claim_next(self.clock.now(), self.worker_id, queues=self.queues)
        if job is None:
            return False
        self._execute(job)
        return True

    def run_forever(self, max_jobs: int | None = None) -> int:
        """Keep running jobs until ``stop()`` is called (or ``max_jobs`` have run)."""
        ran = 0
        log.info("worker %s started (queues=%s)", self.worker_id, self.queues or "all")
        while not self._stop.is_set():
            if self.run_once():
                ran += 1
                if max_jobs is not None and ran >= max_jobs:
                    break
            else:
                self.clock.sleep(self.poll_interval)
        log.info("worker %s stopped after %d jobs", self.worker_id, ran)
        return ran

    def drain(self) -> int:
        """Run jobs until none are due. Handy for tests and `taskmill work --burst`."""
        ran = 0
        while self.run_once():
            ran += 1
        return ran

    def stop(self) -> None:
        self._stop.set()

    # -- internals -------------------------------------------------------

    def _execute(self, job: Job) -> None:
        started = self.clock.now()
        try:
            handler = self.registry.get(job.kind)
        except UnknownJobKind as exc:
            log.error("job #%s: %s", job.id, exc)
            self.store.mark_failed(job.id, self.clock.now(), str(exc))
            self.metrics.incr("jobs.unknown_kind")
            return

        log.debug("job #%s (%s) attempt %d", job.id, job.kind, job.attempts)
        try:
            handler(job.payload)
        except Exception as exc:  # a handler failing must never kill the worker
            log.warning("job #%s (%s) failed: %s", job.id, job.kind, exc)
            now = self.clock.now()
            if job.attempts < MAX_ATTEMPTS:
                delay = RETRY_DELAY * 2 ** (job.attempts - 1)
                self.store.schedule_retry(job.id, now, now + delay, format_error(exc))
            else:
                self.store.mark_failed(job.id, now, format_error(exc))
            self.metrics.incr("jobs.failed")
            self.metrics.incr(f"jobs.failed.{job.kind}")
        else:
            self.store.mark_done(job.id, self.clock.now())
            self.metrics.incr("jobs.done")
            self.metrics.timing(f"jobs.duration.{job.kind}", self.clock.now() - started)
