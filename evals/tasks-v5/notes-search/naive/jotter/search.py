"""Search notes by keyword.

    from jotter.search import search
    for r in search(store, "invoice tag:work"):
        print(r.path, r.score)

Words are matched case-insensitively against the title and body; a title hit
counts double, and recently updated notes get a boost. `tag:NAME` keeps only
notes with that tag.
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jotter import clock

_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Result:
    path: Path
    score: float


def _parse(query):
    words, tags = [], []
    for part in query.split():
        if part.lower().startswith("tag:") and len(part) > 4:
            tags.append(part[4:].lstrip("#").lower())
        else:
            words.extend(_WORD.findall(part.lower()))
    return words, tags


def _recency(note, now):
    updated = note.updated
    if updated is None:
        return 0.0
    age_days = max((now - updated).days, 0)
    return 1.0 / (1.0 + age_days / 30.0)


def search(store, query, limit=20):
    words, tags = _parse(query)
    now = clock.now()
    results = []
    for note in store.notes():
        if tags:
            note_tags = {t.lower() for t in note.tags}
            if not all(t in note_tags for t in tags):
                continue
        title = Counter(_WORD.findall(note.title.lower()))
        body = Counter(_WORD.findall(note.body.lower()))
        score = sum(2 * title[w] + body[w] for w in words)
        if words and score == 0:
            continue
        score = (score or 1) * (1.0 + _recency(note, now))
        results.append(Result(note.path, round(score, 4)))
    results.sort(key=lambda r: (-r.score, str(r.path)))
    return results[:limit]
