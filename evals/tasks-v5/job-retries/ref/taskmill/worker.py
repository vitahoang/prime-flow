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
from .retry import RetryPolicy
from .serialize import format_error
from .store import JobStore

log = logging.getLogger("taskmill.worker")

_seq = itertools.count(1)

#: Who hears about jobs taskmill gives up on (sent as an ordinary email.send job).
OPS_EMAIL = "ops@pebbleprint.example"
#: Thumbnails are regenerated when someone views the file; retrying wastes CPU.
NO_RETRY_KINDS = frozenset({"image.thumbnail"})
#: ...and nobody needs an email about one.
NO_ALERT_KINDS = frozenset({"image.thumbnail"})


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
        retry_policy: RetryPolicy | None = None,
    ):
        self.store = store
        self.registry = registry
        self.clock = clock or SystemClock()
        self.worker_id = worker_id or default_worker_id()
        self.queues = list(queues) if queues else None
        self.poll_interval = poll_interval
        self.metrics = metrics or Metrics()
        self.retry_policy = retry_policy or RetryPolicy()
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
        if job.attempts > self.retry_policy.max_attempts:
            # Reclaimed after its worker died on the last allowed attempt.
            log.error("job #%s: worker lost on final attempt", job.id)
            self._give_up(job, started, job.last_error or "worker lost on final attempt")
            return
        try:
            handler = self.registry.get(job.kind)
        except UnknownJobKind as exc:
            # Usually a deploy in progress: the web app already enqueues a new
            # kind that this worker's code doesn't know yet. Retry as normal.
            log.error("job #%s: %s", job.id, exc)
            self.metrics.incr("jobs.unknown_kind")
            self._failed(job, exc)
            return

        log.debug("job #%s (%s) attempt %d", job.id, job.kind, job.attempts)
        try:
            handler(job.payload)
        except Exception as exc:  # a handler failing must never kill the worker
            self._failed(job, exc)
        else:
            self.store.mark_done(job.id, self.clock.now())
            self.metrics.incr("jobs.done")
            self.metrics.timing(f"jobs.duration.{job.kind}", self.clock.now() - started)

    def _failed(self, job: Job, exc: Exception) -> None:
        now = self.clock.now()
        error = format_error(exc)
        self.metrics.incr("jobs.failed")
        self.metrics.incr(f"jobs.failed.{job.kind}")
        delay = None if job.kind in NO_RETRY_KINDS else self.retry_policy.next_delay(job.attempts, exc)
        if delay is None:
            log.warning("job #%s (%s) is dead after %d attempt(s): %s", job.id, job.kind, job.attempts, exc)
            self._give_up(job, now, error)
        else:
            log.info("job #%s (%s) failed (attempt %d), retrying in %.0fs: %s",
                     job.id, job.kind, job.attempts, delay, exc)
            self.store.schedule_retry(job.id, now, now + delay, error)

    def _give_up(self, job: Job, now: float, error: str) -> None:
        self.store.mark_dead(job.id, now, error)
        self.metrics.incr("jobs.dead")
        if job.kind in NO_ALERT_KINDS or (job.kind == "email.send" and job.payload.get("to") == OPS_EMAIL):
            return  # never alert about a failed alert
        last = error.splitlines()[-1] if error else "-"
        self.store.enqueue("email.send", {
            "to": OPS_EMAIL,
            "subject": f"taskmill gave up on job #{job.id} ({job.kind})",
            "body": f"Job #{job.id} ({job.kind}) is dead after {job.attempts} attempt(s).\n\nLast error: {last}\n",
        }, now=now)
