"""Folder tree helpers."""

from __future__ import annotations

from typing import Iterator, Optional

from .models import Document, Folder


def ancestors(store, folder_id: str) -> list[str]:
    """``folder_id`` and every folder above it, nearest first."""
    chain = []
    cursor: Optional[str] = folder_id
    while cursor is not None:
        chain.append(cursor)
        cursor = store.get_folder(cursor).parent_id
    return chain


def path(store, folder_id: str) -> str:
    names = [store.get_folder(f).name for f in reversed(ancestors(store, folder_id))]
    return "/" + "/".join(names)


def document_path(store, doc_id: str) -> str:
    doc = store.get_document(doc_id)
    return f"{path(store, doc.folder_id)}/{doc.title}"


def children(store, folder_id: Optional[str], workspace_id: Optional[str] = None) -> list[Folder]:
    """Folders directly inside ``folder_id`` (top-level ones when it's None)."""
    out = [f for f in store.folders.values() if f.parent_id == folder_id]
    if workspace_id is not None:
        out = [f for f in out if f.workspace_id == workspace_id]
    return sorted(out, key=lambda f: f.name.lower())


def documents_in(store, folder_id: str, recursive: bool = False,
                 include_trashed: bool = False) -> list[Document]:
    wanted = {folder_id}
    if recursive:
        wanted |= {f.id for f in walk(store, folder_id)}
    docs = [d for d in store.documents.values()
            if d.folder_id in wanted and (include_trashed or not d.trashed)]
    return sorted(docs, key=lambda d: d.title.lower())


def walk(store, folder_id: str) -> Iterator[Folder]:
    """Every folder below ``folder_id`` (not including it), depth first."""
    for child in children(store, folder_id):
        yield child
        yield from walk(store, child.id)


def find(store, workspace_id: str, folder_path: str) -> Optional[Folder]:
    """Resolve "/Projects/Harbour" to a folder, or None."""
    parent = None
    found = None
    for part in [p for p in folder_path.split("/") if p]:
        match = [f for f in children(store, parent, workspace_id) if f.name == part]
        if not match:
            return None
        found = match[0]
        parent = found.id
    return found


def depth(store, folder_id: str) -> int:
    return len(ancestors(store, folder_id)) - 1
