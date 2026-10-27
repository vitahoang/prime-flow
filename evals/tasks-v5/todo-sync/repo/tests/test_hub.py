import pytest

from tickoff.changelog import Change
from tickoff.hub import Hub, NetworkDropped


def ch(device, n):
    return Change(device, n, "2026-10-20T09:00:00Z", f"t{n}", "create", {"title": f"t{n}"})


def test_push_pull():
    hub = Hub()
    assert hub.push("phone", [ch("phone", 1), ch("phone", 2)]) == 2
    hub.push("laptop", [ch("laptop", 1)])
    got, cursor = hub.pull("laptop")
    assert [c.op_id for c in got] == ["phone:1", "phone:2"]
    assert cursor == 3
    got, _ = hub.pull("phone", 0)
    assert [c.op_id for c in got] == ["laptop:1"]
    assert hub.pull("laptop", cursor) == ([], 3)


def test_head_and_stored():
    hub = Hub()
    assert hub.head("phone") == 0
    hub.push("phone", [ch("phone", 3), ch("phone", 7)])
    assert hub.head("phone") == 7
    assert len(hub.stored()) == 2
    assert hub.devices() == ["phone"]


def test_drop_after_stores_what_got_through():
    hub = Hub()
    hub.drop_after(2)
    with pytest.raises(NetworkDropped) as info:
        hub.push("phone", [ch("phone", i) for i in range(1, 6)])
    assert info.value.accepted == 2
    assert [c.lamport for c in hub.stored()] == [1, 2]
    # the fault fires once
    hub.push("phone", [ch("phone", 6)])
    assert len(hub) == 3


def test_drop_counts_across_pushes():
    hub = Hub()
    hub.drop_after(1)
    hub.push("phone", [ch("phone", 1)])
    with pytest.raises(NetworkDropped):
        hub.push("phone", [ch("phone", 2)])
    assert len(hub) == 1


def test_hub_keeps_its_own_copies():
    hub = Hub()
    c = ch("phone", 1)
    hub.push("phone", [c])
    c.fields["title"] = "changed"
    assert hub.stored()[0].fields["title"] == "t1"
