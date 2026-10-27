from datetime import date

from tickoff import query

TODAY = date(2026, 10, 20)


def _setup(replica):
    a = replica.add_task("Late one", due="2026-10-18")
    replica.add_task("Due today", list="work", due="2026-10-20")
    replica.add_task("Next week", due="2026-10-26")
    replica.add_task("Far off", due="2027-01-01")
    d = replica.add_task("Done late", due="2026-10-01")
    replica.complete(d.id)
    return a


def test_overdue(replica):
    _setup(replica)
    assert [t.title for t in query.overdue(replica, TODAY)] == ["Late one"]


def test_due_within(replica):
    _setup(replica)
    assert [t.title for t in query.due_within(replica, TODAY, 7)] == ["Due today", "Next week"]


def test_search(replica):
    _setup(replica)
    assert [t.title for t in query.search(replica, "late")] == ["Late one"]
    assert [t.title for t in query.search(replica, "late", include_done=True)] == ["Late one", "Done late"]


def test_counts(replica):
    _setup(replica)
    assert query.counts(replica) == {"inbox": {"open": 3, "done": 1}, "work": {"open": 1, "done": 0}}


def test_agenda(replica):
    _setup(replica)
    labels = [label for label, _ in query.agenda(replica, TODAY)]
    assert labels == ["overdue", "2026-10-20", "2026-10-26"]
