"""Access checks.

folio has one rule today: the owner of a folder or document can do anything
with it, and nobody else can do anything. Every entry point that touches a
document goes through require_owner (documents.py) or visible_documents
(search.py, cli.py).
"""

from __future__ import annotations

from . import audit, folders, users
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

ROLES = ("viewer", "commenter", "editor")
RANK = {role: i + 1 for i, role in enumerate(ROLES)}
NEEDS = {"read": "viewer", "comment": "commenter", "edit": "editor", "share": "editor"}
GUEST_CAP = "commenter"
HR_FOLDER = "hr"        # anything under a folder called HR is for the HR group only
HR_GROUP = "hr"
ISSUED_FOLDER = "issued"  # anything under a folder called Issued is read/comment only


def grant(store, resource_id: str, principal_id: str, role: str) -> None:
    """Give a user or group ``role`` on a folder or document.

    Granting again to the same principal on the same resource replaces the
    role, which is how someone gets downgraded.
    """
    if role not in RANK:
        raise ValueError(f"unknown role {role!r}; expected one of {', '.join(ROLES)}")
    kind = store.kind_of(resource_id)
    if kind not in (ResourceKind.FOLDER, ResourceKind.DOCUMENT):
        raise NotFound("folder or document", resource_id)
    store.get(resource_id)
    if store.kind_of(principal_id) not in (ResourceKind.USER, ResourceKind.GROUP):
        raise NotFound("user or group", principal_id)
    store.get(principal_id)
    store.grants.setdefault(resource_id, {})[principal_id] = role
    audit.record(store, None, "share.grant", resource_id, principal=principal_id, role=role)


def revoke(store, resource_id: str, principal_id: str) -> None:
    """Remove the grant made to exactly this principal on exactly this resource."""
    shares = store.grants.get(resource_id, {})
    if shares.pop(principal_id, None) is not None:
        audit.record(store, None, "share.revoke", resource_id, principal=principal_id)


def principals_for(store, user_id: str) -> set[str]:
    """The user plus every group they're in, directly or through nesting."""
    found = {user_id}
    frontier = [g.id for g in store.groups.values() if user_id in g.members]
    while frontier:
        gid = frontier.pop()
        if gid in found:
            continue
        found.add(gid)
        frontier.extend(g.id for g in store.groups.values() if gid in g.subgroups)
    return found


def _chain(store, resource_id: str) -> list[str]:
    """Resources whose grants apply to ``resource_id``, nearest first."""
    kind = store.kind_of(resource_id)
    if kind is ResourceKind.DOCUMENT:
        doc = store.get_document(resource_id)
        if doc.restricted:
            return [resource_id]
        return [resource_id] + folders.ancestors(store, doc.folder_id)
    return folders.ancestors(store, resource_id)


def _best_role(store, user_id: str, resource_id: str, guest: bool) -> int:
    if guest:
        # Guests only get what's shared with them by name on this very item.
        role = store.grants.get(resource_id, {}).get(user_id)
        return min(RANK[role], RANK[GUEST_CAP]) if role else 0
    principals = principals_for(store, user_id)
    best = 0
    for rid in _chain(store, resource_id):
        for principal, role in store.grants.get(rid, {}).items():
            if principal in principals:
                best = max(best, RANK[role])
    return best


def _folder_names(store, resource) -> set[str]:
    folder_id = resource.folder_id if isinstance(resource, Document) else resource.id
    return {store.get_folder(f).name.strip().lower() for f in folders.ancestors(store, folder_id)}


def _in_group_named(store, user_id: str, name: str) -> bool:
    mine = principals_for(store, user_id)
    return any(g.id in mine for g in store.groups.values() if g.name.strip().lower() == name)


def can(store, user_id: str, action: str, resource_id: str) -> bool:
    if action not in NEEDS:
        raise ValueError(f"unknown action {action!r}; expected one of {', '.join(NEEDS)}")
    try:
        user = store.get_user(user_id)
        resource = store.get(resource_id)
    except NotFound:
        return False
    if not user.active:
        return False
    owner = is_owner(store, user_id, resource_id)
    if isinstance(resource, Document) and resource.trashed:
        return owner
    if owner:
        return True
    if store.get_workspace(resource.workspace_id).is_admin(user_id):
        return True
    restricted = isinstance(resource, Document) and resource.restricted
    if action == "share" and restricted:
        return False  # only the owner passes on a restricted doc
    names = _folder_names(store, resource)
    if HR_FOLDER in names and not _in_group_named(store, user_id, HR_GROUP):
        return False
    best = _best_role(store, user_id, resource_id, users.is_external(store, user_id))
    if ISSUED_FOLDER in names:
        best = min(best, RANK["commenter"])  # issued work is frozen
    return best >= RANK[NEEDS[action]]
