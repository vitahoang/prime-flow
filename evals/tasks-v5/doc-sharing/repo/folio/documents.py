"""Working with document content: edits, revisions, comments."""

from __future__ import annotations

from . import audit, clock
from .access import require_owner
from .errors import Invalid
from .models import Comment, Revision

MAX_BODY = 1_000_000


def read(store, user_id: str, doc_id: str) -> str:
    require_owner(store, user_id, doc_id, "read")
    doc = store.get_document(doc_id)
    if doc.trashed:
        raise Invalid(f"{doc_id} is in the trash")
    return doc.body


def edit(store, user_id: str, doc_id: str, body: str) -> int:
    """Replace the body and return the new revision number."""
    require_owner(store, user_id, doc_id, "edit")
    doc = store.get_document(doc_id)
    if doc.trashed:
        raise Invalid(f"{doc_id} is in the trash")
    if len(body) > MAX_BODY:
        raise Invalid("document is too large")
    if body == doc.body:
        return doc.revision
    now = clock.now_iso()
    doc.body = body
    doc.revision += 1
    doc.updated = now
    store.revisions.setdefault(doc_id, []).append(Revision(doc_id, doc.revision, body, user_id, now))
    audit.record(store, user_id, "document.edit", doc_id, revision=doc.revision)
    return doc.revision


def rename(store, user_id: str, doc_id: str, title: str) -> None:
    require_owner(store, user_id, doc_id, "rename")
    title = (title or "").strip()
    if not title:
        raise Invalid("document title is empty")
    doc = store.get_document(doc_id)
    old, doc.title = doc.title, title
    doc.updated = clock.now_iso()
    audit.record(store, user_id, "document.rename", doc_id, old=old, new=title)


def history(store, user_id: str, doc_id: str) -> list[Revision]:
    require_owner(store, user_id, doc_id, "read")
    return list(store.revisions.get(doc_id, []))


def revert(store, user_id: str, doc_id: str, number: int) -> int:
    revs = {r.number: r for r in history(store, user_id, doc_id)}
    if number not in revs:
        raise Invalid(f"{doc_id} has no revision {number}")
    return edit(store, user_id, doc_id, revs[number].body)


def add_comment(store, user_id: str, doc_id: str, text: str) -> str:
    require_owner(store, user_id, doc_id, "comment")
    text = (text or "").strip()
    if not text:
        raise Invalid("comment is empty")
    comment = Comment(store.next_comment_id(), doc_id, user_id, text, clock.now_iso())
    store.comments.setdefault(doc_id, []).append(comment)
    audit.record(store, user_id, "comment.add", doc_id, comment=comment.id)
    return comment.id


def resolve_comment(store, user_id: str, doc_id: str, comment_id: str) -> None:
    require_owner(store, user_id, doc_id, "comment")
    for c in store.comments.get(doc_id, []):
        if c.id == comment_id:
            c.resolved = True
            audit.record(store, user_id, "comment.resolve", doc_id, comment=comment_id)
            return
    raise Invalid(f"{doc_id} has no comment {comment_id}")


def open_comments(store, user_id: str, doc_id: str) -> list[Comment]:
    require_owner(store, user_id, doc_id, "read")
    return [c for c in store.comments.get(doc_id, []) if not c.resolved]
