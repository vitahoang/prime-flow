"""Full-text search over a store.

    from jotter.search import search
    for r in search(store, 'invoice "net 30" -paid tag:work'):
        print(r.path, r.score)

Query syntax:
- words: every word must appear in the note (title or body)
- "quoted phrase": the words must appear together, in that order
- -word / -"phrase": notes containing it are left out
- tag:NAME: notes with that tag, matched exactly (case counts: Work is not work)
- archived:yes: include archived notes (they are left out otherwise)

Notes tagged `private` only show up when the query says tag:private. Daily
log notes (named by their date, 2026-04-12.md) come after every other match.

Matching ignores case and accents (cafe finds café). A note whose title
matches ranks above any note that matches only in the body; among equal
matches the most recently updated note comes first.

The first search on a store reads every note once and keeps its words in
memory. Later searches only re-read notes whose file changed; a change is
noticed through the vault folder's mtime, which moves whenever a note is
saved (jotter and most editors save by writing a new file and renaming it),
added or deleted.
"""

import heapq
import os
import re
import unicodedata
import weakref
from dataclasses import dataclass
from pathlib import Path

from jotter import dates, frontmatter, tags as tagmod
from jotter.note import Note

_TOKEN = re.compile(r"\w+")
_QUERY = re.compile(r'(-?)"([^"]*)"?|(\S+)')
_YES = {"yes", "true", "1", "on", "only"}
_DAILY = re.compile(r"\d{4}-\d{2}-\d{2}")
PRIVATE = "private"
TITLE_WEIGHT = 1000.0


@dataclass(frozen=True)
class Result:
    path: Path
    score: float


def fold(text):
    """Lower case, accents removed: 'Café' -> 'cafe'."""
    text = text.lower()
    if text.isascii():
        return text
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text):
    return _TOKEN.findall(fold(text))


# --- the index ----------------------------------------------------------------

class _Doc:
    __slots__ = ("path", "stamp", "title", "body", "terms", "tags", "archived", "updated", "regular")


def _read(path, stamp):
    meta, body = frontmatter.parse(path.read_bytes().decode("utf-8"))
    note = Note(path, meta, body)
    doc = _Doc()
    doc.path = path
    doc.stamp = stamp
    doc.title = tokens(note.title)
    doc.body = tokens(note.body)
    doc.terms = set(doc.title) | set(doc.body)
    if "#" in body:
        doc.tags = tuple(note.tags)
    else:  # no inline #tags possible; skip the scan (it dominates a 30k-note build)
        front = meta.get("tags") or []
        if isinstance(front, str):
            front = [t for t in re.split(r"[,\s]+", front) if t]
        doc.tags = tuple(tagmod.merge(front, ()))
    doc.archived = note.archived
    doc.regular = 0 if _DAILY.fullmatch(path.stem) else 1
    try:
        updated = note.updated
    except dates.BadDate:
        updated = None
    doc.updated = updated.timestamp() if updated else stamp[0] / 1e9
    return doc


def _bad(path, stamp):
    doc = _Doc()
    doc.path, doc.stamp = path, stamp
    doc.title, doc.body, doc.terms, doc.tags = [], [], set(), ()
    doc.archived, doc.updated, doc.regular = False, stamp[0] / 1e9, 1
    return doc


class Index:
    def __init__(self, root):
        self.root = Path(root)
        self.docs = {}
        self._dir_stamp = None

    def refresh(self):
        try:
            st = os.stat(self.root)
        except FileNotFoundError:
            self.docs, self._dir_stamp = {}, None
            return
        if st.st_mtime_ns == self._dir_stamp:
            return
        self._dir_stamp = st.st_mtime_ns
        seen = {}
        with os.scandir(self.root) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith((".", "_")) or not name.endswith(".md") or not entry.is_file():
                    continue
                s = entry.stat()
                seen[Path(entry.path)] = (s.st_mtime_ns, s.st_size, s.st_ino)
        for path in [p for p in self.docs if p not in seen]:
            del self.docs[path]
        for path, stamp in seen.items():
            doc = self.docs.get(path)
            if doc is not None and doc.stamp == stamp:
                continue
            try:
                self.docs[path] = _read(path, stamp)
            except (OSError, UnicodeDecodeError, frontmatter.FrontMatterError):
                self.docs[path] = _bad(path, stamp)


_INDEXES = weakref.WeakKeyDictionary()


def index_for(store):
    index = _INDEXES.get(store)
    if index is None or index.root != Path(store.root):
        index = Index(store.root)
        _INDEXES[store] = index
    index.refresh()
    return index


# --- queries ------------------------------------------------------------------

@dataclass
class Query:
    terms: list      # each a tuple of tokens; length 1 = word, more = phrase
    excluded: list
    tags: list
    archived: bool = False


def parse(text):
    q = Query([], [], [])
    for m in _QUERY.finditer(text):
        minus, quoted, bare = m.group(1), m.group(2), m.group(3)
        if bare is not None:
            key, sep, value = bare.partition(":")
            if sep and value and key.lower() == "tag":
                q.tags.append(tagmod.clean(value))
                continue
            if sep and value and key.lower() == "archived":
                q.archived = value.lower() in _YES
                continue
            minus = "-" if bare.startswith("-") and len(bare) > 1 else ""
            quoted = bare[1:] if minus else bare
        words = tuple(tokens(quoted))
        if not words:
            continue
        (q.excluded if minus else q.terms).append(words)
    return q


def _occurrences(seq, term):
    if len(term) == 1:
        return seq.count(term[0])
    n, k = 0, len(term)
    first = term[0]
    for i in range(len(seq) - k + 1):
        if seq[i] == first and tuple(seq[i:i + k]) == term:
            n += 1
    return n


def _has_tag(doc, tag):
    return any(t == tag or t.startswith(tag + "/") for t in doc.tags)


def search(store, query, limit=20):
    """Notes matching `query`, best first, at most `limit` of them."""
    index = index_for(store)
    q = parse(query)
    required = {w for term in q.terms for w in term}
    scored = []
    for doc in index.docs.values():
        if required and not required <= doc.terms:
            continue
        if doc.archived and not q.archived:
            continue
        if q.tags and not all(_has_tag(doc, t) for t in q.tags):
            continue
        if PRIVATE in doc.tags and PRIVATE not in q.tags:
            continue
        if any(_occurrences(doc.title, t) or _occurrences(doc.body, t) for t in q.excluded):
            continue
        score = 0.0
        ok = True
        for term in q.terms:
            in_title = _occurrences(doc.title, term)
            in_body = _occurrences(doc.body, term)
            if not (in_title or in_body):
                ok = False
                break
            score += (TITLE_WEIGHT if in_title else 0.0) + min(in_body, 100) / (1.0 + len(doc.body) / 200.0)
        if ok:
            scored.append((score, doc.updated, str(doc.path), doc.regular))
    best = heapq.nlargest(limit, scored, key=lambda s: (s[3], s[0], s[1])) if limit else []
    return [Result(Path(p), round(score, 4)) for score, _, p, _ in best]
