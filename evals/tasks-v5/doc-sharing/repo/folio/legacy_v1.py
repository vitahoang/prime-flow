"""Importer for folio v1 exports.

v1 had no folders: every document carried a "path" string, and a "private"
flag. The migration ran in March; this is kept in case another v1 export turns
up. Nothing imports it.
"""

from __future__ import annotations

from .store import Store


def import_v1(store: Store, workspace_id: str, export: dict) -> dict[str, str]:
    """Load a v1 export into ``workspace_id``. Returns v1 id -> new doc id."""
    by_email = {u.email: u.id for u in store.users_in_workspace(workspace_id)}
    folder_ids: dict[tuple, str] = {}
    mapping = {}
    for item in export.get("documents", []):
        owner = by_email.get(item.get("owner", "").lower())
        if owner is None:
            owner = store.add_user(workspace_id, item["owner"])
            by_email[item["owner"].lower()] = owner
        parts = [p for p in item.get("path", "").split("/") if p] or ["Imported"]
        parent = None
        for i in range(len(parts)):
            key = tuple(parts[: i + 1])
            if key not in folder_ids:
                folder_ids[key] = store.create_folder(workspace_id, parts[i], owner, parent)
            parent = folder_ids[key]
        doc_id = store.create_document(parent, item.get("title") or "Untitled", owner,
                                       item.get("text", ""))
        if item.get("private"):
            store.set_restricted(doc_id)
        mapping[item["id"]] = doc_id
    return mapping


def _v1_perm_to_role(perm: str) -> str:
    # v1 had "r", "rw" and "rwc"; never wired up after the migration.
    return {"r": "viewer", "rw": "editor", "rwc": "editor"}.get(perm, "viewer")
