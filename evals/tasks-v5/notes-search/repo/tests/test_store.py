from jotter.store import NoteNotFound, Store

from conftest import write_note


def test_create_and_load(store):
    note = store.create("Café à Montréal", tags=["food"], body="Good.\n")
    assert note.path.name == "cafe-a-montreal.md"
    again = Store(store.root).load(note.path)
    assert again.title == "Café à Montréal"
    assert again.tags == ["food"]
    assert again.meta["created"] == "2026-05-01T10:00:00"


def test_duplicate_titles_get_suffix(store):
    a = store.create("Same")
    b = store.create("Same")
    assert a.path.name == "same.md"
    assert b.path.name == "same-2.md"


def test_paths_ignore_hidden_and_underscore(store):
    store.create("Kept")
    write_note(store.root, ".hidden.md", "x")
    write_note(store.root, "_draft.md", "x")
    write_note(store.root, "notes.txt", "x")
    assert [p.name for p in store.paths()] == ["kept.md"]


def test_get_by_name_slug_title(store):
    note = store.create("Garden Plan")
    assert store.get("garden-plan").path == note.path
    assert store.get("garden-plan.md").path == note.path
    assert store.get("garden plan").path == note.path
    try:
        store.get("nope")
    except NoteNotFound:
        pass
    else:
        raise AssertionError("expected NoteNotFound")


def test_save_touches_updated(store, monkeypatch):
    note = store.create("Draft")
    monkeypatch.setenv("JOTTER_NOW", "2026-06-01T08:00:00")
    note.body = "more\n"
    store.save(note)
    assert Store(store.root).load(note.path).meta["updated"] == "2026-06-01T08:00:00"


def test_rename_moves_file(store):
    note = store.create("Old name")
    old = note.path
    store.rename(note, "New name")
    assert not old.exists()
    assert note.path.name == "new-name.md"


def test_notes_without_archived(store):
    a = store.create("Live")
    b = store.create("Gone")
    b.meta["archived"] = True
    store.save(b)
    assert [n.path for n in store.notes(include_archived=False)] == [a.path]


def test_sample_vault_loads(sample):
    notes = sample.notes()
    assert len(notes) >= 25
    assert all(n.title for n in notes)
