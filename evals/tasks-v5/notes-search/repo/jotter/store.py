"""The notes store: one folder of `.md` files.

Every `*.md` file directly inside the vault folder is a note. Files and
folders starting with `.` or `_` are ignored (editors and sync tools leave
those around). Sub-folders are not scanned.
"""

import os
from pathlib import Path

from jotter import clock, dates
from jotter.note import Note
from jotter.textutil import slugify


class NoteNotFound(LookupError):
    pass


class Store:
    def __init__(self, root):
        self.root = Path(root)
        # Parsed notes, keyed by path and mtime so an edit made in the editor
        # is picked up on the next load.
        self._cache = {}

    def __repr__(self):
        return f"Store({str(self.root)!r})"

    # --- reading ------------------------------------------------------------

    def paths(self):
        """Paths of all notes, sorted by file name."""
        if not self.root.is_dir():
            return []
        out = []
        with os.scandir(self.root) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith((".", "_")) or not name.endswith(".md"):
                    continue
                if entry.is_file():
                    out.append(Path(entry.path))
        return sorted(out)

    def load(self, path):
        path = Path(path)
        cached = self._cache.get(path)
        if cached is not None:
            return cached[1]
        note = Note.read(path)
        self._cache[path] = (path.stat().st_mtime, note)
        return note

    def notes(self, include_archived=True):
        out = []
        for path in self.paths():
            note = self.load(path)
            if include_archived or not note.archived:
                out.append(note)
        return out

    def get(self, name):
        """Find a note by file name (with or without .md), slug or title."""
        name = str(name)
        candidates = [self.root / name, self.root / (name + ".md"), self.root / (slugify(name) + ".md")]
        for path in candidates:
            if path.is_file():
                return self.load(path)
        for note in self.notes():
            if note.title.lower() == name.lower() or name.lower() in (a.lower() for a in note.aliases):
                return note
        raise NoteNotFound(name)

    # --- writing ------------------------------------------------------------

    def path_for(self, title):
        """A free file name for a new note with this title."""
        stem = slugify(title)
        path = self.root / f"{stem}.md"
        n = 2
        while path.exists():
            path = self.root / f"{stem}-{n}.md"
            n += 1
        return path

    def create(self, title, tags=(), body=""):
        now = dates.format(clock.now())
        meta = {"title": title, "tags": list(tags), "created": now, "updated": now}
        note = Note(self.path_for(title), meta, body)
        self.save(note, touch=False)
        return note

    def save(self, note, touch=True):
        """Write a note. `touch` bumps `updated` to now."""
        if touch:
            note.meta["updated"] = dates.format(clock.now())
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = note.path.with_name("." + note.path.name + ".tmp")
        tmp.write_text(note.to_text(), encoding="utf-8")
        os.replace(tmp, note.path)
        self._cache[note.path] = (note.path.stat().st_mtime, note)
        return note

    def delete(self, note):
        self._cache.pop(note.path, None)
        note.path.unlink()

    def rename(self, note, new_title):
        """Change a note's title and file name. Links elsewhere are not rewritten."""
        old_path = note.path
        note.meta["title"] = new_title
        note.path = self.path_for(new_title)
        self.save(note)
        if old_path != note.path:
            self._cache.pop(old_path, None)
            old_path.unlink()
        return note

    def forget(self):
        """Drop every cached note."""
        self._cache.clear()
