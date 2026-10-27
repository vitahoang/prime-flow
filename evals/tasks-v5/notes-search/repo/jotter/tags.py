"""Tags.

A note's tags are the `tags:` list in its front matter plus any inline
`#tag` in the body (outside code). Tags may be nested with `/`
(`clients/dupont`); a nested tag also counts under its parents.
"""

import re
from collections import defaultdict

INLINE = re.compile(r"(?<![\w&/#])#([A-Za-zÀ-ɏ][\w\-/À-ɏ]*)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def clean(tag):
    """'#clients/dupont ' -> 'clients/dupont'."""
    return str(tag).strip().lstrip("#").strip("/")


def inline_tags(body):
    """#tags in the body, skipping fenced code blocks and inline `code`."""
    found = []
    in_code = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r"`[^`]*`", "", line)
        found.extend(m.group(1).rstrip("/-") for m in INLINE.finditer(line))
    return found


def merge(front, inline):
    """Front-matter tags first, then inline ones; duplicates dropped."""
    seen = []
    for tag in list(front) + list(inline):
        tag = clean(tag)
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def parents(tag):
    """'a/b/c' -> ['a', 'a/b']."""
    parts = tag.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


class TagIndex:
    """tag -> set of note paths, for a set of notes."""

    def __init__(self, notes=()):
        self._paths = defaultdict(set)
        for note in notes:
            self.add(note)

    def add(self, note):
        for tag in note.tags:
            self._paths[tag].add(note.path)
            for parent in parents(tag):
                self._paths[parent].add(note.path)

    def paths(self, tag):
        return set(self._paths.get(clean(tag), ()))

    def counts(self):
        return {tag: len(paths) for tag, paths in self._paths.items()}

    def __contains__(self, tag):
        return clean(tag) in self._paths

    def __iter__(self):
        return iter(sorted(self._paths))


def add_tag(note, tag):
    """Add a tag to the note's front matter. Returns True if it changed."""
    tag = clean(tag)
    current = [clean(t) for t in _front_list(note)]
    if tag in current:
        return False
    note.meta["tags"] = current + [tag]
    return True


def remove_tag(note, tag):
    """Remove a front-matter tag. Inline #tags in the body are left alone."""
    tag = clean(tag)
    current = [clean(t) for t in _front_list(note)]
    if tag not in current:
        return False
    note.meta["tags"] = [t for t in current if t != tag]
    return True


def rename_tag(store, old, new):
    """Rename a front-matter tag across the vault. Returns the notes changed."""
    changed = []
    for note in store.notes():
        if remove_tag(note, old):
            add_tag(note, new)
            store.save(note, touch=False)
            changed.append(note)
    return changed


def _front_list(note):
    value = note.meta.get("tags", [])
    if isinstance(value, str):
        return [t for t in re.split(r"[,\s]+", value) if t]
    return list(value)
