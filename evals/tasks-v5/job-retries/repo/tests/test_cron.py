from taskmill.cron import Schedule


def test_cron_fires_once_per_slot(store, clock):
    sched = Schedule(store)
    sched.every(3600, "report.daily")
    assert sched.tick(clock.now()) == 0
    clock.advance(1800)
    assert sched.tick(clock.now()) == 0
    clock.advance(1800)
    assert sched.tick(clock.now()) == 1
    assert sched.tick(clock.now()) == 0
    assert len(store.list(kind="report.daily")) == 1
