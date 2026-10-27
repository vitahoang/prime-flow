import pytest

from ledger import storage
from ledger.models import Entry


def test_missing_file_is_empty(home):
    assert storage.load_entries() == []


def test_round_trip_sorted_by_time(home):
    entries = [
        Entry(2, "2026-02-01T10:00:00Z", "Later", -500),
        Entry(1, "2026-01-01T10:00:00Z", "Café supplies", 1500, "office", True),
    ]
    storage.save_entries(entries)
    loaded = storage.load_entries()
    assert [e.id for e in loaded] == [1, 2]
    assert loaded[0].description == "Café supplies"
    assert loaded[0].archived is True


def test_next_id(home):
    assert storage.next_id([]) == 1
    assert storage.next_id([Entry(7, "2026-01-01T00:00:00Z", "x", 1)]) == 8


def test_rejects_unknown_version(home):
    (home / "entries.json").write_text('{"version": 99, "entries": []}')
    with pytest.raises(ValueError):
        storage.load_entries()
