"""Title and full-text search over the documents a user can see."""

from __future__ import annotations

from dataclasses import dataclass

from .access import visible_documents
from .folders import document_path
from .textutil import snippet


@dataclass
class Hit:
    doc_id: str
    path: str
    score: int
    snippet: str


def search(store, user_id: str, query: str, limit: int = 20) -> list[Hit]:
    query = (query or "").strip()
    if not query:
        return []
    q = query.lower()
    hits = []
    for doc in visible_documents(store, user_id):
        score = 0
        if q in doc.title.lower():
            score += 10
            if doc.title.lower().startswith(q):
                score += 5
        count = doc.body.lower().count(q)
        score += min(count, 5)
        if score:
            hits.append(Hit(doc.id, document_path(store, doc.id), score, snippet(doc.body, query)))
    hits.sort(key=lambda h: (-h.score, h.path.lower()))
    return hits[:limit]
