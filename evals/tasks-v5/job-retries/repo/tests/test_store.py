import sqlite3

import pytest

from taskmill.errors import InvalidTransition, JobNotFound
from taskmill.store import SCHEMA_VERSION, JobStore


def test_enqueue_and_get(store, clock):
    job = store.enqueue("email.send", {"to": "a@b.c"}, now=clock.now())
    got = store.get(job.id)
    assert got.kind == "email.send"
    assert got.payload == {"to": "a@b.c"}
    assert got.status == "queued"
    assert got.attempts == 0
    assert got.run_at == clock.now()


def test_claim_respects_run_at(store, clock):
    store.enqueue("later", run_at=clock.now() + 60, now=clock.now())
    assert store.claim_next(clock.now(), "w1") is None
    clock.advance(60)
    job = store.claim_next(clock.now(), "w1")
    assert job.kind == "later"
    assert job.status == "running"
    assert job.attempts == 1
    assert job.worker_id == "w1"
    assert job.started_at == clock.now()


def test_claim_order_priority_then_run_at(store, clock):
    now = clock.now()
    a = store.enqueue("a", run_at=now - 10, now=now)
    b = store.enqueue("b", run_at=now - 20, now=now)
    c = store.enqueue("c", run_at=now - 5, priority=5, now=now)
    order = [store.claim_next(now, "w").id for _ in range(3)]
    assert order == [c.id, b.id, a.id]
    assert store.claim_next(now, "w") is None


def test_claim_filters_queues(store, clock):
    now = clock.now()
    store.enqueue("a", queue="mail", now=now)
    b = store.enqueue("b", queue="images", now=now)
    assert store.claim_next(now, "w", queues=["images"]).id == b.id
    assert store.claim_next(now, "w", queues=["images"]) is None


def test_mark_done_and_failed(store, clock):
    now = clock.now()
    a = store.enqueue("a", now=now)
    b = store.enqueue("b", now=now)
    store.mark_done(a.id, now + 1)
    store.mark_failed(b.id, now + 2, "Traceback...\nValueError: nope")
    assert store.get(a.id).status == "done"
    assert store.get(a.id).finished_at == now + 1
    fb = store.get(b.id)
    assert fb.status == "failed"
    assert fb.last_error.endswith("nope")


def test_requeue_only_failed_or_cancelled(store, clock):
    now = clock.now()
    job = store.enqueue("a", now=now)
    with pytest.raises(InvalidTransition):
        store.requeue(job.id, now)
    store.mark_failed(job.id, now, "x")
    again = store.requeue(job.id, now + 5)
    assert again.status == "queued"
    assert again.run_at == now + 5


def test_cancel(store, clock):
    job = store.enqueue("a", now=clock.now())
    assert store.cancel(job.id, clock.now()).status == "cancelled"
    with pytest.raises(InvalidTransition):
        store.cancel(job.id, clock.now())


def test_get_or_raise(store):
    with pytest.raises(JobNotFound):
        store.get_or_raise(999)


def test_counts_and_purge(store, clock):
    now = clock.now()
    a = store.enqueue("a", now=now)
    store.enqueue("b", now=now)
    store.mark_done(a.id, now)
    assert store.counts()["done"] == 1
    assert store.counts()["queued"] == 1
    assert store.counts()["failed"] == 0
    assert store.purge(now + 1) == 1
    assert store.get(a.id) is None


def test_events_recorded(store, clock):
    job = store.enqueue("a", now=clock.now())
    store.claim_next(clock.now(), "w1")
    store.mark_done(job.id, clock.now())
    assert [e["event"] for e in store.events(job.id)] == ["enqueued", "claimed", "done"]


def test_migrations_upgrade_old_file(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    from taskmill.store import MIGRATIONS
    conn.executescript(MIGRATIONS[0] + "\nPRAGMA user_version = 1;")
    conn.execute("INSERT INTO jobs (kind, run_at, created_at, updated_at) VALUES ('x', 0, 0, 0)")
    conn.commit()
    conn.close()
    with JobStore(path) as s:
        job = s.list()[0]
        assert job.priority == 0 and job.queue == "default"
        assert s._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_iter_all_batches(store, clock):
    for i in range(7):
        store.enqueue("a", {"i": i}, now=clock.now())
    assert [j.payload["i"] for j in store.iter_all(batch=3)] == list(range(7))
