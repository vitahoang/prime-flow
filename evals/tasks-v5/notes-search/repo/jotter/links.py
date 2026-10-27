"""[[Wiki links]] between notes.

`[[Target]]`, `[[Target|label]]` and `[[Target#Heading]]` are recognised.
Links are resolved by note title, falling back to the file name.
"""

import re

from jotter.textutil import slugify

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]*))?(?:\|([^\]]*))?\]\]")


def extract(body):
    """Link targets in the order they appear (duplicates kept)."""
    return [m.group(1).strip() for m in WIKILINK.finditer(body)]


def target_key(target):
    return slugify(target)


def resolve(store, target):
    """The path a link points at, or None if it is broken."""
    key = target_key(target)
    for path in store.paths():
        if path.stem == key:
            return path
    return None


def outgoing(store, note):
    """[(target text, resolved path or None)] for one note."""
    return [(t, resolve(store, t)) for t in extract(note.body)]


def backlinks(store, note):
    """Notes that link to `note`."""
    key = note.path.stem
    result = []
    for other in store.notes():
        if other.path == note.path:
            continue
        if any(target_key(t) == key for t in extract(other.body)):
            result.append(other)
    return result


def broken(store):
    """[(note, target)] for every link that resolves to nothing."""
    stems = {p.stem for p in store.paths()}
    out = []
    for note in store.notes():
        for target in extract(note.body):
            if target_key(target) not in stems:
                out.append((note, target))
    return out


def rewrite_target(body, old, new):
    """Point links at `old` to `new`, keeping labels and headings."""
    old_key = target_key(old)

    def repl(m):
        if target_key(m.group(1)) != old_key:
            return m.group(0)
        out = "[[" + new
        if m.group(2) is not None:
            out += "#" + m.group(2)
        if m.group(3) is not None:
            out += "|" + m.group(3)
        return out + "]]"

    return WIKILINK.sub(repl, body)
