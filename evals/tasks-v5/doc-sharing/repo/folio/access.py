"""Access checks.

folio has one rule today: the owner of a folder or document can do anything
with it, and nobody else can do anything. Every entry point that touches a
document goes through require_owner (documents.py) or visible_documents
(search.py, cli.py).
"""

from __future__ import annotations

from .errors import AccessDenied, NotFound
from .models import Document, ResourceKind


def owner_of(store, resource_id: str) -> str:
    kind = store.kind_of(resource_id)
    if kind is ResourceKind.DOCUMENT:
        return store.get_document(resource_id).owner_id
    if kind is ResourceKind.FOLDER:
        return store.get_folder(resource_id).owner_id
    raise NotFound("folder or document", resource_id)


def is_owner(store, user_id: str, resource_id: str) -> bool:
    try:
        return owner_of(store, resource_id) == user_id
    except NotFound:
        return False


def require_owner(store, user_id: str, resource_id: str, action: str = "change") -> None:
    if not is_owner(store, user_id, resource_id):
        raise AccessDenied(user_id, action, resource_id)


def visible_documents(store, user_id: str) -> list[Document]:
    """Documents ``user_id`` may open, trash excluded."""
    return [d for d in store.documents.values() if not d.trashed and d.owner_id == user_id]


def trash_of(store, user_id: str) -> list[Document]:
    """The user's own trashed documents."""
    return [d for d in store.documents.values() if d.trashed and d.owner_id == user_id]
