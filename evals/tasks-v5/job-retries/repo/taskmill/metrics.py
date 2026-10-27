"""Tiny in-process counters and timings.

Each worker keeps its own ``Metrics``; ``taskmill stats`` reads the database
instead, so these are only for logs and the periodic summary line.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Timing:
    count: int = 0
    total: float = 0.0
    max: float = 0.0

    def add(self, seconds: float) -> None:
        self.count += 1
        self.total += seconds
        self.max = max(self.max, seconds)

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else 0.0


@dataclass
class Metrics:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    timings: dict[str, Timing] = field(default_factory=lambda: defaultdict(Timing))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def incr(self, name: str, by: int = 1) -> None:
        with self._lock:
            self.counters[name] += by

    def timing(self, name: str, seconds: float) -> None:
        with self._lock:
            self.timings[name].add(seconds)

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "timings": {k: {"count": t.count, "mean": round(t.mean, 4), "max": round(t.max, 4)}
                            for k, t in self.timings.items()},
            }

    def summary_line(self) -> str:
        done, failed = self.get("jobs.done"), self.get("jobs.failed")
        return f"done={done} failed={failed} unknown={self.get('jobs.unknown_kind')}"

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.timings.clear()
