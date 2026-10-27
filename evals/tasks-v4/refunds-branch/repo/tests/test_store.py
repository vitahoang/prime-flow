import json

import pytest

from payouts.errors import NotFound
from payouts.store import Store


def test_insert_and_get(store):
    store.insert("things", {"id": "t_1", "x": 1})
    assert store.get("things", "t_1") == {"id": "t_1", "x": 1}


def test_get_missing(store):
    with pytest.raises(NotFound):
        store.get("things", "nope")


def test_duplicate_id(store):
    store.insert("things", {"id": "t_1"})
    with pytest.raises(ValueError):
        store.insert("things", {"id": "t_1"})


def test_update(store):
    store.insert("things", {"id": "t_1", "x": 1})
    store.update("things", "t_1", x=2)
    assert store.get("things", "t_1")["x"] == 2


def test_persisted_as_json(tmp_path):
    Store(tmp_path).insert("things", {"id": "t_1"})
    assert json.loads((tmp_path / "things.json").read_text()) == [{"id": "t_1"}]
    assert Store(tmp_path).get("things", "t_1") == {"id": "t_1"}


def test_next_id_sequential(store):
    assert store.next_id("ch") == "ch_0001"
    assert store.next_id("ch") == "ch_0002"
    assert store.next_id("m") == "m_0001"


def test_bad_table_name(store):
    with pytest.raises(ValueError):
        store.load("../etc")


def test_default_dir_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYOUTS_DATA_DIR", str(tmp_path / "data"))
    s = Store()
    assert s.root == tmp_path / "data"
    assert s.root.is_dir()


def test_no_temp_files_left(store, tmp_path):
    store.insert("things", {"id": "t_1"})
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []
