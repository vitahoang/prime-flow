"""`jotter check`: find notes with problems."""

from collections import defaultdict

from jotter import dates, links
from jotter.config import KNOWN_KEYS
from jotter.frontmatter import FrontMatterError
from jotter.note import Note


def problems(store):
    """[(path name, message)], sorted by path."""
    out = []
    titles = defaultdict(list)
    notes = []
    for path in store.paths():
        try:
            note = Note.read(path)
        except FrontMatterError as exc:
            out.append((path.name, f"bad front matter: {exc}"))
            continue
        except UnicodeDecodeError:
            out.append((path.name, "not UTF-8"))
            continue
        notes.append(note)
        if not note.meta.get("title"):
            out.append((path.name, "no title in front matter"))
        try:
            created, updated = note.created, note.updated
        except dates.BadDate as exc:
            out.append((path.name, str(exc)))
            created = updated = None
        if note.meta and created is None:
            out.append((path.name, "no created date"))
        if created and updated and updated < created:
            out.append((path.name, "updated is before created"))
        unknown = [k for k in note.meta if k not in KNOWN_KEYS]
        if unknown:
            out.append((path.name, "unknown keys: " + ", ".join(unknown)))
        titles[note.title.lower()].append(path.name)
    for title, names in titles.items():
        if len(names) > 1:
            for name in names:
                out.append((name, f"duplicate title {title!r}"))
    stems = {p.stem for p in store.paths()}
    for note in notes:
        for target in note.links:
            if links.target_key(target) not in stems:
                out.append((note.path.name, f"broken link [[{target}]]"))
    return sorted(out)
