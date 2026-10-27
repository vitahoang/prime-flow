"""Saving and loading a Store as JSON.

The file is one object with a key per table. Ids are kept as they are, and the
store's id counters are moved past the highest id loaded.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Comment, Document, Event, Folder, Group, Revision, User, UserStatus, Workspace
from .store import Store

FORMAT = 2


def dump(store: Store) -> dict:
    return {
        "format": FORMAT,
        "workspaces": [asdict(w) for w in store.workspaces.values()],
        "users": [dict(asdict(u), status=u.status.value) for u in store.users.values()],
        "groups": [asdict(g) for g in store.groups.values()],
        "folders": [asdict(f) for f in store.folders.values()],
        "documents": [asdict(d) for d in store.documents.values()],
        "comments": [asdict(c) for cs in store.comments.values() for c in cs],
        "revisions": [asdict(r) for rs in store.revisions.values() for r in rs],
        "events": [asdict(e) for e in store.events],
    }


def load(data: dict) -> Store:
    fmt = data.get("format", 1)
    if fmt != FORMAT:
        raise ValueError(f"unsupported store format {fmt} (expected {FORMAT})")
    s = Store()
    for w in data.get("workspaces", []):
        s.workspaces[w["id"]] = Workspace(**w)
    for u in data.get("users", []):
        s.users[u["id"]] = User(**dict(u, status=UserStatus(u.get("status", "active"))))
    for g in data.get("groups", []):
        s.groups[g["id"]] = Group(**g)
    for f in data.get("folders", []):
        s.folders[f["id"]] = Folder(**f)
    for d in data.get("documents", []):
        s.documents[d["id"]] = Document(**d)
        s.comments.setdefault(d["id"], [])
        s.revisions.setdefault(d["id"], [])
    for c in data.get("comments", []):
        s.comments.setdefault(c["document_id"], []).append(Comment(**c))
    for r in data.get("revisions", []):
        s.revisions.setdefault(r["document_id"], []).append(Revision(**r))
    s.events = [Event(**e) for e in data.get("events", [])]
    for table in (s.workspaces, s.users, s.groups, s.folders, s.documents):
        for ident in table:
            s.ids.bump_past(ident)
    s._comment_seq = sum(len(cs) for cs in s.comments.values())
    return s


def save(store: Store, path) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dump(store), indent=2, sort_keys=True))
    tmp.replace(path)


def load_file(path) -> Store:
    return load(json.loads(Path(path).read_text()))
