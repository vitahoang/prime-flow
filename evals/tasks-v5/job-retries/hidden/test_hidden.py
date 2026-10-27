"""Acceptance tests for retries in taskmill.

Entry point: ``taskmill.worker.Worker(store, registry, clock).run_once()``,
built from the repo's own ``JobStore(path)``, ``Registry()`` and
``FakeClock(start)``. Jobs are read back with ``store.get(id)`` and judged
only by ``status``, ``attempts`` and ``run_at``.

A "delay" is ``run_at - clock.now()`` read right after the failing
``run_once()``; the FakeClock doesn't move while a handler runs.

Isolation: each id's tests depend only on that id's rule.
- Clock moves go to the job's own ``run_at`` (+1s), so no test depends on a
  particular backoff except H2's.
- Retry counts stay at 2 failures or fewer outside H2/H3, so any limit of 3+
  attempts works.
- PermanentError (H4) and RateLimited (H5) tests accept "dead" or "failed";
  only H6 requires the name "dead". H8 checks alerts only, never statuses.
- Jobs taskmill enqueues itself (H8's alert emails) have no handler in these
  registries; tests only count calls of their own handlers, so a worker that
  picks one up between our jobs changes nothing.
"""

import collections
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from taskmill.clock import FakeClock
from taskmill.errors import PermanentError, RateLimited
from taskmill.registry import Registry
from taskmill.store import JobStore
from taskmill.worker import Worker

ROOT = Path(__file__).resolve().parent
T0 = 1_767_225_600.0  # 2026-01-01T00:00:00Z
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}


def st(job):
    return getattr(job.status, "value", job.status)


class Handler:
    """Raises the given exceptions in order (None = succeed), then `then`."""

    def __init__(self, *script, then=None):
        self.script = list(script)
        self.then = then
        self.calls = 0

    def __call__(self, payload):
        self.calls += 1
        exc = self.script.pop(0) if self.script else self.then
        if exc is not None:
            raise exc


def boom():
    return RuntimeError("partner returned 503")


def make(tmp_path, handler, kind="partner.sync", start=T0):
    store = JobStore(tmp_path / "jobs.db")
    reg = Registry()
    reg.register(kind, handler)
    clock = FakeClock(start)
    return store, Worker(store, reg, clock), clock


def add(store, clock, kind="partner.sync", payload=None):
    return store.enqueue(kind, payload or {}, run_at=clock.now(), now=clock.now()).id


def delay_of(store, clock, job_id):
    return store.get(job_id).run_at - clock.now()


def wait_until_due(store, clock, job_id):
    """Move the clock to just after the job's run_at (at least 1s)."""
    run_at = store.get(job_id).run_at
    gap = run_at - clock.now() if run_at is not None else 0
    clock.advance(min(max(gap, 0), 2 * 86_400) + 1)


def drive(worker, store, clock, job_id, rounds):
    for _ in range(rounds):
        worker.run_once()
        if st(store.get(job_id)) == "done":
            return
        wait_until_due(store, clock, job_id)


# ---------------------------------------------------------------- E

def test_E1_failing_job_retried_until_success(tmp_path):
    h = Handler(boom(), boom(), None)
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    drive(w, store, clock, job_id, rounds=10)
    assert st(store.get(job_id)) == "done"
    assert h.calls == 3


def test_E2_retry_is_later_not_immediate(tmp_path):
    h = Handler(boom(), None)
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    w.run_once()
    job = store.get(job_id)
    assert job.attempts == 1
    assert st(job) != "done"
    assert job.run_at > clock.now()
    w.run_once()  # same instant: not due yet
    assert h.calls == 1


# ---------------------------------------------------------------- T1: two workers, one file

CHILD_DRAIN = r"""
import json, os, sys, time
from taskmill.clock import FakeClock
from taskmill.registry import Registry
from taskmill.store import JobStore
from taskmill.worker import Worker
db, flag, now = sys.argv[1], sys.argv[2], float(sys.argv[3])
ran = []
def work(payload):
    ran.append(payload["n"])
    time.sleep(0.0005)
reg = Registry()
reg.register("order.export", work)
w = Worker(JobStore(db), reg, FakeClock(now))
while not os.path.exists(flag):
    time.sleep(0.001)
idle, deadline = 0, time.time() + 90
while idle < 3 and time.time() < deadline:
    if w.run_once():
        idle = 0
    else:
        idle += 1
        time.sleep(0.005)
print(json.dumps(ran))
"""

N_RACE = 400


def _fill(db):
    store = JobStore(db)
    ids = [store.enqueue("order.export", {"n": n}, run_at=T0, now=T0).id for n in range(N_RACE)]
    return store, ids


def _check_once_each(store, ids, ran):
    counts = collections.Counter(ran)
    twice = sorted(n for n, c in counts.items() if c > 1)
    assert not twice, f"{len(twice)} job(s) ran more than once, e.g. {twice[:5]}"
    assert set(counts) == set(range(N_RACE))
    assert all(st(store.get(i)) == "done" for i in ids)


def test_T1_two_worker_processes_never_run_a_job_twice(tmp_path):
    db = str(tmp_path / "jobs.db")
    store, ids = _fill(db)
    flag = tmp_path / "go"
    procs = [subprocess.Popen([sys.executable, "-c", CHILD_DRAIN, db, str(flag), str(T0 + 5)],
                              cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for _ in range(2)]
    time.sleep(0.5)
    flag.write_text("go")
    ran = []
    for p in procs:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err[-2000:]
        ran += json.loads(out.strip().splitlines()[-1])
    _check_once_each(store, ids, ran)


def test_T1_two_worker_threads_never_run_a_job_twice(tmp_path):
    db = str(tmp_path / "jobs.db")
    store, ids = _fill(db)
    ran, lock, go, errors = [], threading.Lock(), threading.Event(), []

    def body():
        try:
            def work(payload):
                with lock:
                    ran.append(payload["n"])
                time.sleep(0.0005)

            reg = Registry()
            reg.register("order.export", work)
            w = Worker(JobStore(db), reg, FakeClock(T0 + 5))
            go.wait()
            idle = 0
            while idle < 3:
                if w.run_once():
                    idle = 0
                else:
                    idle += 1
                    time.sleep(0.005)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(repr(exc))

    threads = [threading.Thread(target=body) for _ in range(2)]
    for t in threads:
        t.start()
    time.sleep(0.2)
    go.set()
    for t in threads:
        t.join(120)
    assert not errors, errors
    _check_once_each(store, ids, ran)


# ---------------------------------------------------------------- H1: worker killed mid-job

CHILD_HANG = r"""
import sys, time
from pathlib import Path
from taskmill.clock import FakeClock
from taskmill.registry import Registry
from taskmill.store import JobStore
from taskmill.worker import Worker
db, flag, now = sys.argv[1], sys.argv[2], float(sys.argv[3])
def hang(payload):
    Path(flag).write_text("started")
    time.sleep(300)
reg = Registry()
reg.register("report.build", hang)
Worker(JobStore(db), reg, FakeClock(now)).run_once()
"""


def _killed_mid_job(tmp_path):
    """Enqueue a job at T0, let a real worker process start it at T0, kill -9 it."""
    db = tmp_path / "jobs.db"
    store = JobStore(db)
    job_id = store.enqueue("report.build", {}, run_at=T0, now=T0).id
    flag = tmp_path / "started"
    p = subprocess.Popen([sys.executable, "-c", CHILD_HANG, str(db), str(flag), str(T0)],
                         cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + 30
    while not flag.exists():
        assert p.poll() is None, p.stderr.read().decode()[-2000:]
        assert time.time() < deadline, "worker never started the job"
        time.sleep(0.01)
    p.kill()
    p.wait()
    return store, job_id


def _after_crash(tmp_path, minutes):
    store, job_id = _killed_mid_job(tmp_path)
    h = Handler()
    reg = Registry()
    reg.register("report.build", h)
    clock = FakeClock(T0 + minutes * 60)
    return store, Worker(store, reg, clock), clock, job_id, h


def test_H1_job_of_killed_worker_retried_after_lease(tmp_path):
    store, w, clock, job_id, h = _after_crash(tmp_path, minutes=11)
    for _ in range(3):
        w.run_once()
        if st(store.get(job_id)) == "done":
            break
        wait_until_due(store, clock, job_id)
    assert h.calls == 1
    assert st(store.get(job_id)) == "done"


def test_H1_killed_run_counts_as_one_attempt(tmp_path):
    store, w, clock, job_id, h = _after_crash(tmp_path, minutes=11)
    for _ in range(3):
        w.run_once()
        if st(store.get(job_id)) == "done":
            break
        wait_until_due(store, clock, job_id)
    assert st(store.get(job_id)) == "done"
    assert store.get(job_id).attempts == 2


def test_H1_running_job_not_taken_before_ten_minutes(tmp_path):
    store, w, clock, job_id, h = _after_crash(tmp_path, minutes=9)
    w.run_once()
    assert h.calls == 0, "a job still within its 10 minutes was taken from its worker"
    clock.set(T0 + 11 * 60)
    for _ in range(3):
        w.run_once()
        if st(store.get(job_id)) == "done":
            break
        wait_until_due(store, clock, job_id)
    assert h.calls == 1


# ---------------------------------------------------------------- H2: backoff

def test_H2_backoff_30s_doubling(tmp_path):
    h = Handler(then=boom())
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    delays = []
    for _ in range(4):
        w.run_once()
        d = delay_of(store, clock, job_id)
        if d <= 0:
            break  # gave up
        delays.append(d)
        clock.advance(d + 1)
    assert len(delays) >= 2, delays
    for i, d in enumerate(delays):
        expected = min(30 * 2 ** i, 3600)
        assert expected * 0.9 - 0.01 <= d <= expected * 1.1 + 0.01, (i + 1, d, delays)


def test_H2_jitter_spreads_retries(tmp_path):
    h = Handler(then=boom())
    store, w, clock = make(tmp_path, h)
    ids = [add(store, clock) for _ in range(40)]
    for _ in ids:
        w.run_once()
    delays = [delay_of(store, clock, i) for i in ids]
    assert all(27 - 0.01 <= d <= 33 + 0.01 for d in delays), sorted(delays)
    assert len({round(d, 6) for d in delays}) > 1, "all 40 retries scheduled for the same instant"


# ---------------------------------------------------------------- H3: five attempts; H6: then dead

def _always_failing(tmp_path):
    h = Handler(then=boom())
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    for _ in range(12):
        w.run_once()
        wait_until_due(store, clock, job_id)
    clock.advance(2 * 86_400)
    for _ in range(3):
        w.run_once()
    return store, job_id, h


def test_H3_five_attempts_in_total(tmp_path):
    store, job_id, h = _always_failing(tmp_path)
    assert h.calls == 5
    assert store.get(job_id).attempts == 5


def test_H3_fifth_attempt_still_happens(tmp_path):
    h = Handler(boom(), boom(), boom(), boom(), None)
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    drive(w, store, clock, job_id, rounds=10)
    assert h.calls == 5
    assert st(store.get(job_id)) == "done"


def test_H6_gives_up_as_dead(tmp_path):
    store, job_id, h = _always_failing(tmp_path)
    assert st(store.get(job_id)) == "dead"


def test_H6_dead_job_stays_dead(tmp_path):
    store, job_id, h = _always_failing(tmp_path)
    calls = h.calls
    w = Worker(store, Registry(), FakeClock(T0 + 10 * 86_400))
    for _ in range(3):
        w.run_once()
    assert st(store.get(job_id)) == "dead"
    assert h.calls == calls


# ---------------------------------------------------------------- H4: PermanentError

class CustomerDeleted(PermanentError):
    pass


def _permanent_vs_plain(tmp_path, permanent):
    """One job raises `permanent`; another fails once with a plain error, then works."""
    store = JobStore(tmp_path / "jobs.db")
    perm, plain = Handler(then=permanent), Handler(boom(), None)
    reg = Registry()
    reg.register("order.export", perm)
    reg.register("partner.sync", plain)
    clock = FakeClock(T0)
    w = Worker(store, reg, clock)
    a = add(store, clock, "order.export")
    b = add(store, clock, "partner.sync")
    for _ in range(8):
        w.run_once()
        w.run_once()
        clock.advance(2 * 3600)
    return store, a, b, perm, plain


def test_H4_permanent_error_never_retried(tmp_path):
    store, a, b, perm, plain = _permanent_vs_plain(tmp_path, PermanentError("payload has no order id"))
    assert plain.calls == 2 and st(store.get(b)) == "done"  # ordinary errors do retry
    assert perm.calls == 1
    assert store.get(a).attempts == 1


def test_H4_permanent_error_subclass_gives_up_at_once(tmp_path):
    store, a, b, perm, plain = _permanent_vs_plain(tmp_path, CustomerDeleted("customer 812 was deleted"))
    assert st(store.get(b)) == "done"
    assert perm.calls == 1
    assert st(store.get(a)) in ("dead", "failed")


# ---------------------------------------------------------------- H5: RateLimited.retry_after

def test_H5_retry_after_longer_than_backoff_is_honoured(tmp_path):
    h = Handler(RateLimited(retry_after=600), None)
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    w.run_once()
    d = delay_of(store, clock, job_id)
    assert 540 - 0.01 <= d <= 660 + 0.01, d  # 10% jitter may sit on either side (brief: your call)


def test_H5_retry_after_on_a_later_attempt(tmp_path):
    h = Handler(boom(), RateLimited(retry_after=900), None)
    store, w, clock = make(tmp_path, h)
    job_id = add(store, clock)
    w.run_once()
    wait_until_due(store, clock, job_id)
    w.run_once()
    assert h.calls == 2
    d = delay_of(store, clock, job_id)
    assert 810 - 0.01 <= d <= 990 + 0.01, d


def test_H5_short_retry_after_keeps_normal_backoff(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    reg = Registry()
    reg.register("plain", Handler(boom(), None))
    reg.register("limited", Handler(RateLimited(retry_after=1), None))
    clock = FakeClock(T0)
    w = Worker(store, reg, clock)
    a = add(store, clock, "plain")
    b = add(store, clock, "limited")
    w.run_once()
    w.run_once()
    da, db_ = delay_of(store, clock, a), delay_of(store, clock, b)
    assert da > 0 and db_ > 0
    assert 0.5 <= db_ / da <= 2.0, (da, db_)


# ---------------------------------------------------------------- H7: no handler yet (deploy in progress)

def test_H7_job_with_no_handler_is_retried_not_given_up(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    clock = FakeClock(T0)
    w = Worker(store, Registry(), clock)
    job_id = add(store, clock, "lab.refund")
    w.run_once()
    job = store.get(job_id)
    assert st(job) not in ("dead", "failed", "done")
    assert job.run_at > clock.now()


def test_H7_job_runs_once_the_handler_exists(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    reg = Registry()
    clock = FakeClock(T0)
    w = Worker(store, reg, clock)
    job_id = add(store, clock, "lab.refund")
    w.run_once()  # old worker code: no handler for this kind yet
    h = Handler()
    reg.register("lab.refund", h)  # the deploy finishes
    drive(w, store, clock, job_id, rounds=6)
    assert h.calls == 1
    assert st(store.get(job_id)) == "done"


# ---------------------------------------------------------------- H8: ops hears about jobs we give up on

OPS = "ops@pebbleprint.example"
JOB_NO = 777


def _start_ids_at(tmp_path, n):
    """Make the next job id `n` so it can't be confused with line numbers etc."""
    store = JobStore(tmp_path / "jobs.db")
    clock = FakeClock(T0)
    filler = store.enqueue("filler", {}, run_at=T0 + 10 * 86_400, now=T0).id
    store.cancel(filler, T0)
    conn = sqlite3.connect(tmp_path / "jobs.db")
    conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'jobs'", (n - 1,))
    conn.commit()
    conn.close()
    return store, clock


def _alerts(store, job_no):
    out = []
    for job in store.list(kind="email.send", limit=1000):
        p = job.payload
        text = f"{p.get('subject', '')} {p.get('body', '')}"
        if p.get("to") == OPS and re.search(rf"(?<!\d){job_no}(?!\d)", text):
            out.append(job)
    return out


def test_H8_ops_emailed_when_retries_run_out(tmp_path):
    store, clock = _start_ids_at(tmp_path, JOB_NO)
    reg = Registry()
    reg.register("partner.sync", Handler(then=boom()))
    reg.register("order.export", Handler(boom(), None))
    w = Worker(store, reg, clock)
    dying = add(store, clock, "partner.sync")
    recovering = add(store, clock, "order.export")
    assert dying == JOB_NO
    for _ in range(15):
        w.run_once()
        w.run_once()
        clock.advance(2 * 3600)
    assert st(store.get(recovering)) == "done"
    assert len(_alerts(store, dying)) == 1, [j.payload for j in store.list(kind="email.send")]
    assert _alerts(store, recovering) == []  # a job that recovered is not reported


def test_H8_ops_emailed_for_permanent_error(tmp_path):
    store, clock = _start_ids_at(tmp_path, JOB_NO)
    reg = Registry()
    reg.register("order.export", Handler(then=PermanentError("order 5521 was deleted")))
    w = Worker(store, reg, clock)
    job_id = add(store, clock, "order.export")
    for _ in range(8):
        w.run_once()
        clock.advance(2 * 3600)
    assert len(_alerts(store, job_id)) == 1


# ---------------------------------------------------------------- H9: thumbnails are never retried

def _thumb_vs_plain(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    thumb, plain = Handler(then=OSError("corrupt upload")), Handler(boom(), None)
    reg = Registry()
    reg.register("image.thumbnail", thumb)
    reg.register("partner.sync", plain)
    clock = FakeClock(T0)
    w = Worker(store, reg, clock)
    a = add(store, clock, "image.thumbnail")
    b = add(store, clock, "partner.sync")
    return store, w, clock, a, b, thumb, plain


def test_H9_failed_thumbnail_not_retried(tmp_path):
    store, w, clock, a, b, thumb, plain = _thumb_vs_plain(tmp_path)
    for _ in range(8):
        w.run_once()
        w.run_once()
        clock.advance(2 * 3600)
    assert st(store.get(b)) == "done" and plain.calls == 2  # other kinds still retry
    assert thumb.calls == 1


def test_H9_failed_thumbnail_given_up_at_once(tmp_path):
    store, w, clock, a, b, thumb, plain = _thumb_vs_plain(tmp_path)
    w.run_once()
    w.run_once()
    assert st(store.get(a)) in ("dead", "failed")
    job_b = store.get(b)
    assert st(job_b) not in ("dead", "failed") and job_b.run_at > clock.now()
