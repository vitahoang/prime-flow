import json

import pytest

from tickoff.replica import Replica
from tickoff.storage import StorageError, load_replica


def test_save_and_load_roundtrip(tmp_path, replica, errands, wall):
    replica.complete(errands[0])
    replica.sync_state["note"] = "kept"
    path = tmp_path / "laptop.json"
    replica.save(path)
    again = Replica.load(path, wall=wall)
    assert again.device_id == "laptop"
    assert [t.title for t in again.list_tasks("errands")] == [t.title for t in replica.list_tasks("errands")]
    assert again.get(errands[0]).done
    assert len(again.log) == len(replica.log)
    assert again.clock.value == replica.clock.value
    assert again.sync_state == {"note": "kept"}


def test_counter_continues_after_load(tmp_path, replica, errands, wall):
    path = tmp_path / "laptop.json"
    replica.save(path)
    again = Replica.load(path, wall=wall)
    again.add_task("more")
    assert again.log.last().lamport == replica.clock.value + 1


def test_format_1_is_upgraded(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"device": "phone", "items": [
        {"id": "a1", "name": "Old task", "position": 2, "done": True},
    ]}))
    r = load_replica(path)
    assert r.get("a1").title == "Old task"
    assert r.get("a1").order == 2
    assert r.get("a1").done


def test_errors(tmp_path):
    with pytest.raises(StorageError):
        load_replica(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    with pytest.raises(StorageError):
        load_replica(bad)
    newer = tmp_path / "newer.json"
    newer.write_text(json.dumps({"format": 9, "device": "x"}))
    with pytest.raises(StorageError):
        load_replica(newer)


def test_samples_load():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "samples"
    lap = load_replica(root / "laptop.json")
    phone = load_replica(root / "phone.json")
    assert lap.device_id == "laptop" and phone.device_id == "phone"
    assert lap.lists() and phone.lists()
