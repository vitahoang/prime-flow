from tickoff.changelog import Change, ChangeLog


def test_every_local_change_is_logged(replica, wall):
    t = replica.add_task("Buy stamps")
    wall.advance()
    replica.complete(t.id)
    replica.delete_task(t.id)
    kinds = [c.kind for c in replica.log]
    assert kinds == ["create", "update", "delete"]
    assert [c.lamport for c in replica.log] == [1, 2, 3]
    assert replica.log[1].fields == {"done": True}
    assert all(c.device == "laptop" for c in replica.log)


def test_op_ids_are_unique(replica):
    for i in range(5):
        replica.add_task(f"task {i}")
    ids = [c.op_id for c in replica.log]
    assert len(set(ids)) == len(ids)
    assert ids[0] == "laptop:1"


def test_no_change_no_entry(replica):
    t = replica.add_task("Buy stamps")
    replica.edit_task(t.id, title="Buy stamps")
    assert len(replica.log) == 1


def test_change_roundtrip():
    c = Change("phone", 4, "2026-10-20T09:00:00Z", "abc", "update", {"due": None})
    assert Change.from_dict(c.to_dict()) == c


def test_since_and_history(replica):
    t = replica.add_task("A")
    replica.rename(t.id, "B")
    replica.add_task("C")
    assert [c.lamport for c in replica.log.since(1)] == [2, 3]
    assert len(replica.log.history(t.id)) == 2
    assert "created 'A'" in replica.log.history(t.id)[0]


def test_from_list_empty():
    assert len(ChangeLog.from_list(None)) == 0
