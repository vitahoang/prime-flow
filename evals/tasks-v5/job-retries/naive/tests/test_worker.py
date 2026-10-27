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


def test_failed_job_is_retried_then_failed(store, registry, clock):
    def boom(payload):
        raise ValueError("partner down")

    registry.register("boom", boom)
    job = store.enqueue("boom", now=clock.now())
    w = Worker(store, registry, clock)
    w.run_once()
    got = store.get(job.id)
    assert got.status == "queued"
    assert got.run_at == clock.now() + 60
    for _ in range(5):
        clock.advance(1000)
        w.run_once()
    got = store.get(job.id)
    assert got.status == "failed" and got.attempts == 3
    assert "partner down" in got.last_error


def test_unknown_kind_fails_job(store, registry, clock):
    job = store.enqueue("nobody.home", now=clock.now())
    Worker(store, registry, clock).run_once()
    got = store.get(job.id)
    assert got.status == "failed"
    assert "no handler" in got.last_error


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
