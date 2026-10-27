"""People helpers."""

from __future__ import annotations


def is_external(store, user_id: str) -> bool:
    """True for guests: accounts whose email isn't on the workspace's domain."""
    user = store.get_user(user_id)
    ws = store.get_workspace(user.workspace_id)
    return user.domain != ws.domain


def display(store, user_id: str) -> str:
    user = store.get_user(user_id)
    tags = []
    if is_external(store, user_id):
        tags.append("guest")
    if not user.active:
        tags.append(user.status.value)
    if store.get_workspace(user.workspace_id).is_admin(user_id):
        tags.append("admin")
    suffix = f" ({', '.join(tags)})" if tags else ""
    return f"{user.name} <{user.email}>{suffix}"


def find_by_email(store, workspace_id: str, email: str):
    email = (email or "").strip().lower()
    for u in store.users.values():
        if u.workspace_id == workspace_id and u.email == email:
            return u
    return None
