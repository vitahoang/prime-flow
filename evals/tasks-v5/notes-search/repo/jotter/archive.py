"""Archiving notes.

An archived note has `archived: true` in its front matter. It stays in the
vault folder, keeps its links, and is hidden from `jotter list` unless
`--archived` is given.
"""

import shutil

ARCHIVE_DIR = "_archive"


def archive(store, note):
    if note.archived:
        return False
    note.meta["archived"] = True
    store.save(note, touch=False)
    return True


def unarchive(store, note):
    if not note.archived:
        return False
    note.meta.pop("archived", None)
    store.save(note, touch=False)
    return True


def archived_notes(store):
    return [n for n in store.notes() if n.archived]


def archive_older_than(store, cutoff, dry_run=True):
    """Archive notes last updated before `cutoff` (a datetime)."""
    picked = [n for n in store.notes(include_archived=False) if n.updated and n.updated < cutoff]
    if not dry_run:
        for note in picked:
            archive(store, note)
    return picked


def move_to_archive_dir(store, note):
    """Before 0.7 archiving moved the file into _archive/. Kept for the
    migration script; nothing calls it any more."""
    target = store.root / ARCHIVE_DIR
    target.mkdir(exist_ok=True)
    shutil.move(str(note.path), str(target / note.path.name))
    return target / note.path.name
