import pytest

from tickoff.models import ValidationError
from tickoff.replica import Replica

from .conftest import titles


def test_add_and_list(replica):
    replica.add_task("Buy stamps")
    replica.add_task("Call the bank")
    assert titles(replica) == ["Buy stamps", "Call the bank"]


def test_insert_at_position(replica, errands):
    replica.add_task("Pick up keys", list="errands", position=1)
    replica.add_task("First thing", list="errands", position=0)
    assert titles(replica, "errands") == ["First thing", "Buy stamps", "Pick up keys",
                                          "Call the bank", "Post the parcel"]


def test_move_within_list(replica, errands):
    replica.move_task(errands[2], 0)
    assert titles(replica, "errands") == ["Post the parcel", "Buy stamps", "Call the bank"]
    replica.move_task(errands[2], 5)
    assert titles(replica, "errands") == ["Buy stamps", "Call the bank", "Post the parcel"]


def test_move_to_other_list(replica, errands):
    replica.add_task("Inbox thing")
    replica.move_task(errands[0], 0, list="inbox")
    assert titles(replica) == ["Buy stamps", "Inbox thing"]
    assert titles(replica, "errands") == ["Call the bank", "Post the parcel"]


def test_edit_list_puts_task_at_end(replica, errands):
    replica.add_task("Inbox thing")
    replica.edit_task(errands[1], list="inbox")
    assert titles(replica) == ["Inbox thing", "Call the bank"]


def test_complete_reopen(replica):
    t = replica.add_task("x")
    replica.complete(t.id)
    assert replica.get(t.id).done
    replica.reopen(t.id)
    assert not replica.get(t.id).done
    assert [x.title for x in replica.list_tasks(include_done=False)] == ["x"]


def test_delete(replica, errands):
    replica.delete_task(errands[1])
    assert replica.get(errands[1]) is None
    with pytest.raises(KeyError):
        replica.complete(errands[1])


def test_find(replica, errands):
    assert replica.find("call the bank").id == errands[1]
    assert replica.find(errands[0][:5]).id == errands[0]
    with pytest.raises(KeyError):
        replica.find("nope")


def test_explicit_ids(replica):
    replica.add_task("x", task_id="t-1")
    with pytest.raises(ValueError):
        replica.add_task("y", task_id="t-1")
    with pytest.raises(ValueError):
        replica.add_task("y", task_id="Bad Id")


def test_bad_values_rejected(replica):
    with pytest.raises(ValidationError):
        replica.add_task("x", due="soon")
    t = replica.add_task("x")
    with pytest.raises(ValidationError):
        replica.edit_task(t.id, title="")


def test_updated_at_follows_wall(replica, wall):
    t = replica.add_task("x")
    wall.advance(600)
    replica.complete(t.id)
    assert t.updated_at == "2026-10-20T09:10:00Z"
    assert t.created_at == "2026-10-20T09:00:00Z"


def test_bad_device_id():
    with pytest.raises(ValueError):
        Replica("My Phone")


def test_lists_inbox_first(replica):
    replica.add_task("a", list="work")
    replica.add_task("b", list="errands")
    replica.add_task("c")
    assert replica.lists() == ["inbox", "errands", "work"]
