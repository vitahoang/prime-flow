"""Access checks.

folio has one rule today: the owner of a folder or document can do anything
with it, and nobody else can do anything. Every entry point that touches a
document goes through require_owner (documents.py) or visible_documents
(search.py, cli.py).
"""

from __future__ import annotations

from . import folders, groups
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


# -- sharing -----------------------------------------------------------------

ROLES = {"viewer": 1, "commenter": 2, "editor": 3}
# Sharing changes who can see a document, so it stays with the owner, like
# every other management action in folio.
NEEDS = {"read": 1, "comment": 2, "edit": 3, "share": None}


def _shares(store) -> list:
    if not hasattr(store, "shares"):
        store.shares = []
    return store.shares


def _people(store, principal_id: str) -> list[str]:
    if store.kind_of(principal_id) is ResourceKind.GROUP:
        return groups.direct_members(store, principal_id)
    store.get_user(principal_id)
    return [principal_id]


def grant(store, resource_id: str, principal_id: str, role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    store.get(resource_id)
    for user_id in _people(store, principal_id):
        _shares(store).append((resource_id, user_id, role))


def revoke(store, resource_id: str, principal_id: str) -> None:
    people = set(_people(store, principal_id))
    store.shares = [s for s in _shares(store) if not (s[0] == resource_id and s[1] in people)]


def can(store, user_id: str, action: str, resource_id: str) -> bool:
    if action not in NEEDS:
        raise ValueError(f"unknown action {action!r}")
    if is_owner(store, user_id, resource_id):
        return True
    need = NEEDS[action]
    if need is None:
        return False
    if store.kind_of(resource_id) is ResourceKind.DOCUMENT:
        chain = [resource_id] + folders.ancestors(store, store.get_document(resource_id).folder_id)
    else:
        chain = folders.ancestors(store, resource_id)
    # The most specific grant wins: a share on the document overrides the folder's.
    for rid in chain:
        roles = [ROLES[r] for res, uid, r in _shares(store) if res == rid and uid == user_id]
        if roles:
            return max(roles) >= need
    return False
