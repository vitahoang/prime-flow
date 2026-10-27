from taskmill.worker import Worker


def test_run_once_runs_due_job(store, registry, clock):
    seen = []
    registry.register("greet", lambda p: seen.append(p["name"]))
    job = store.enqueue("greet", {"name": "ana"}, now=clock.now())
    w = Worker(store, registry, clock)
    assert w.run_once() is True
    assert seen == ["ana"]
    assert store.get(job.id).status == "done"
    assert w.run_once() is False


def test_failed_job_is_retried_with_backoff(store, registry, clock):
    def boom(payload):
        raise ValueError("partner down")

    registry.register("boom", boom)
    job = store.enqueue("boom", now=clock.now())
    w = Worker(store, registry, clock)
    w.run_once()
    got = store.get(job.id)
    assert got.status == "queued"
    assert got.attempts == 1
    assert 30 <= got.run_at - clock.now() <= 33
    assert "partner down" in got.last_error
    assert w.metrics.get("jobs.failed") == 1


def test_dead_after_five_attempts(store, registry, clock):
    calls = []
    registry.register("boom", lambda p: calls.append(1) or 1 / 0)
    job = store.enqueue("boom", now=clock.now())
    w = Worker(store, registry, clock)
    for _ in range(10):
        w.run_once()
        clock.advance(3700)
    assert len(calls) == 5
    assert store.get(job.id).status == "dead"


def test_permanent_error_not_retried(store, registry, clock):
    from taskmill.errors import PermanentError

    def bad(p):
        raise PermanentError("customer deleted")

    registry.register("bad", bad)
    job = store.enqueue("bad", now=clock.now())
    Worker(store, registry, clock).run_once()
    assert store.get(job.id).status == "dead"


def test_rate_limited_waits_retry_after(store, registry, clock):
    from taskmill.errors import RateLimited

    def slow_down(p):
        raise RateLimited(retry_after=900)

    registry.register("hook", slow_down)
    job = store.enqueue("hook", now=clock.now())
    Worker(store, registry, clock).run_once()
    assert store.get(job.id).run_at - clock.now() == 900


def test_backoff_doubles_and_caps():
    from taskmill.retry import RetryPolicy

    p = RetryPolicy(jitter=0)
    assert [p.backoff(n) for n in (1, 2, 3, 8, 9)] == [30, 60, 120, 3600, 3600]


def test_stuck_job_reclaimed_after_lease(store, registry, clock):
    registry.register("t", lambda p: None)
    job = store.enqueue("t", now=clock.now())
    store.claim_next(clock.now(), "dead-worker")  # its worker never comes back
    w = Worker(store, registry, clock)
    clock.advance(599)
    assert w.run_once() is False
    clock.advance(2)
    assert w.run_once() is True
    got = store.get(job.id)
    assert got.status == "done" and got.attempts == 2


def test_two_stores_never_claim_same_job(tmp_path, clock):
    from taskmill.store import JobStore

    a, b = JobStore(tmp_path / "j.db"), JobStore(tmp_path / "j.db")
    job = a.enqueue("t", now=clock.now())
    # Once a holds the job, b must not get it too.
    assert a.claim_next(clock.now(), "a").id == job.id
    assert b.claim_next(clock.now(), "b") is None


def test_unknown_kind_is_retried(store, registry, clock):
    job = store.enqueue("nobody.home", now=clock.now())
    Worker(store, registry, clock).run_once()
    got = store.get(job.id)
    assert got.status == "queued" and got.run_at > clock.now()
    assert "no handler" in got.last_error


def test_dead_job_alerts_ops(store, registry, clock):
    from taskmill.errors import PermanentError

    def bad(p):
        raise PermanentError("x")

    registry.register("bad", bad)
    job = store.enqueue("bad", now=clock.now())
    Worker(store, registry, clock).run_once()
    [mail] = store.list(kind="email.send")
    assert mail.payload["to"] == "ops@pebbleprint.example"
    assert f"#{job.id}" in mail.payload["subject"]


def test_thumbnails_not_retried_or_alerted(store, registry, clock):
    registry.register("image.thumbnail", lambda p: 1 / 0)
    job = store.enqueue("image.thumbnail", now=clock.now())
    Worker(store, registry, clock).run_once()
    assert store.get(job.id).status == "dead"
    assert store.list(kind="email.send") == []


def test_future_job_waits(store, registry, clock):
    registry.register("later", lambda p: None)
    store.enqueue("later", run_at=clock.now() + 30, now=clock.now())
    w = Worker(store, registry, clock)
    assert w.run_once() is False
    clock.advance(30)
    assert w.run_once() is True


def test_run_forever_sleeps_when_idle(store, registry, clock):
    registry.register("t", lambda p: None)
    store.enqueue("t", run_at=clock.now() + 5, now=clock.now())
    w = Worker(store, registry, clock, poll_interval=1.0)
    assert w.run_forever(max_jobs=1) == 1
    assert clock.sleeps == [1.0] * 5


def test_drain(store, registry, clock):
    registry.register("t", lambda p: None)
    for _ in range(4):
        store.enqueue("t", now=clock.now())
    assert Worker(store, registry, clock).drain() == 4


def test_queues_limit_what_worker_takes(store, registry, clock):
    registry.register("t", lambda p: None)
    store.enqueue("t", queue="mail", now=clock.now())
    w = Worker(store, registry, clock, queues=["images"])
    assert w.run_once() is False


def test_handler_exception_does_not_stop_loop(store, registry, clock):
    calls = []

    def flaky(p):
        calls.append(p["n"])
        if p["n"] == 1:
            raise RuntimeError("x")

    registry.register("f", flaky)
    for n in range(3):
        store.enqueue("f", {"n": n}, now=clock.now())
    assert Worker(store, registry, clock).drain() == 3
    assert calls == [0, 1, 2]
