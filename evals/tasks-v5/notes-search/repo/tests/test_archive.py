from datetime import datetime

from jotter import archive
from jotter.store import Store


def test_archive_and_undo(store):
    note = store.create("Old thing")
    assert archive.archive(store, note)
    assert not archive.archive(store, note)
    assert Store(store.root).load(note.path).archived
    assert archive.unarchive(store, note)
    assert not Store(store.root).load(note.path).archived


def test_archive_older_than(store, monkeypatch):
    monkeypatch.setenv("JOTTER_NOW", "2020-01-01T00:00:00")
    old = store.create("Old")
    monkeypatch.setenv("JOTTER_NOW", "2026-01-01T00:00:00")
    store.create("New")
    picked = archive.archive_older_than(store, datetime(2025, 1, 1), dry_run=False)
    assert [n.path for n in picked] == [old.path]
    assert [n.title for n in archive.archived_notes(store)] == ["Old"]
