"""Run several worker processes and keep them alive.

``taskmill supervise`` starts ``config.workers`` processes. Each one opens its
own JobStore on the shared database file and runs ``Worker.run_forever``.
If a worker process dies, the supervisor starts a new one.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import signal
import time
from dataclasses import dataclass

from .config import Config

log = logging.getLogger("taskmill.supervisor")

RESTART_BACKOFF = 2.0  # seconds to wait before restarting a crashed worker


def _worker_main(cfg: Config, index: int) -> None:
    # Imported here so the parent never opens the database itself.
    from .logging_setup import configure
    from .registry import Registry
    from .store import JobStore
    from .worker import Worker, default_worker_id

    configure(cfg.log_level)
    registry = Registry()
    registry.load_modules(cfg.handler_modules)
    store = JobStore(cfg.database)
    worker = Worker(store, registry, worker_id=f"{default_worker_id()}#{index}",
                    queues=cfg.queues or None, poll_interval=cfg.poll_interval)
    signal.signal(signal.SIGTERM, lambda *_: worker.stop())
    try:
        worker.run_forever()
    finally:
        store.close()


@dataclass
class Slot:
    index: int
    process: mp.Process | None = None
    restarts: int = 0
    last_start: float = 0.0


class Supervisor:
    def __init__(self, cfg: Config, *, context: str = "spawn"):
        self.cfg = cfg
        self.ctx = mp.get_context(context)
        self.slots = [Slot(i) for i in range(cfg.workers)]
        self._stopping = False

    def start(self) -> None:
        for slot in self.slots:
            self._start(slot)

    def _start(self, slot: Slot) -> None:
        p = self.ctx.Process(target=_worker_main, args=(self.cfg, slot.index),
                             name=f"taskmill-worker-{slot.index}", daemon=False)
        p.start()
        slot.process, slot.last_start = p, time.monotonic()
        log.info("started worker %d (pid %s)", slot.index, p.pid)

    def check(self) -> None:
        """Restart any worker that has exited."""
        for slot in self.slots:
            p = slot.process
            if p is None or p.is_alive() or self._stopping:
                continue
            log.warning("worker %d exited with code %s", slot.index, p.exitcode)
            if time.monotonic() - slot.last_start < RESTART_BACKOFF:
                time.sleep(RESTART_BACKOFF)
            slot.restarts += 1
            self._start(slot)

    def stop(self, timeout: float = 5.0) -> None:
        self._stopping = True
        for slot in self.slots:
            if slot.process and slot.process.is_alive():
                slot.process.terminate()
        deadline = time.monotonic() + timeout
        for slot in self.slots:
            if slot.process:
                slot.process.join(max(0.0, deadline - time.monotonic()))
                if slot.process.is_alive():
                    slot.process.kill()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "_stopping", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "_stopping", True))
        self.start()
        log.info("supervising %d workers on %s", len(self.slots), self.cfg.database)
        try:
            while not self._stopping:
                self.check()
                time.sleep(0.5)
        finally:
            self.stop()
