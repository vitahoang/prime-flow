"""The in-memory store.

A Store holds every workspace, user, group, folder and document, and is the
only thing that creates them. Persistence lives in serialize.py.

Typical setup::

    s = Store()
    ws = s.add_workspace("Hollis & Grey", domain="hollisgrey.com")
    olive = s.add_user(ws, "olive@hollisgrey.com", "Olive")
    projects = s.create_folder(ws, "Projects", olive)
    doc = s.create_document(projects, "Site visit notes", olive)
"""

from __future__ import annotations

from typing import Iterable, Optional

from . import audit, clock
from .errors import Invalid, NotFound
from .ids import IdSource, kind_of
from .models import (
    Comment,
    Document,
    Folder,
    Group,
    ResourceKind,
    Revision,
    User,
    UserStatus,
    Workspace,
)


class Store:
    def __init__(self) -> None:
        self.workspaces: dict[str, Workspace] = {}
        self.users: dict[str, User] = {}
        self.groups: dict[str, Group] = {}
        self.folders: dict[str, Folder] = {}
        self.documents: dict[str, Document] = {}
        self.comments: dict[str, list[Comment]] = {}
        self.revisions: dict[str, list[Revision]] = {}
        self.events: list = []
        # resource id -> {principal id: role}; managed by access.grant / revoke
        self.grants: dict[str, dict[str, str]] = {}
        self.ids = IdSource()
        self._comment_seq = 0

    # -- lookups ---------------------------------------------------------------

    def get_workspace(self, ws_id: str) -> Workspace:
        try:
            return self.workspaces[ws_id]
        except KeyError:
            raise NotFound("workspace", ws_id) from None

    def get_user(self, user_id: str) -> User:
        try:
            return self.users[user_id]
        except KeyError:
            raise NotFound("user", user_id) from None

    def get_group(self, group_id: str) -> Group:
        try:
            return self.groups[group_id]
        except KeyError:
            raise NotFound("group", group_id) from None

    def get_folder(self, folder_id: str) -> Folder:
        try:
            return self.folders[folder_id]
        except KeyError:
            raise NotFound("folder", folder_id) from None

    def get_document(self, doc_id: str) -> Document:
        try:
            return self.documents[doc_id]
        except KeyError:
            raise NotFound("document", doc_id) from None

    def kind_of(self, ident: str) -> ResourceKind:
        kind = kind_of(ident)
        if kind is None:
            raise NotFound("resource", ident)
        return kind

    def get(self, ident: str):
        """Look up anything by id."""
        kind = self.kind_of(ident)
        table = {
            ResourceKind.WORKSPACE: self.get_workspace,
            ResourceKind.USER: self.get_user,
            ResourceKind.GROUP: self.get_group,
            ResourceKind.FOLDER: self.get_folder,
            ResourceKind.DOCUMENT: self.get_document,
        }[kind]
        return table(ident)

    def exists(self, ident: str) -> bool:
        try:
            self.get(ident)
        except NotFound:
            return False
        return True

    # -- workspaces and people -------------------------------------------------

    def add_workspace(self, name: str, domain: str) -> str:
        name = (name or "").strip()
        domain = (domain or "").strip().lower().lstrip("@")
        if not name:
            raise Invalid("workspace name is empty")
        if not domain or "." not in domain:
            raise Invalid(f"bad domain {domain!r}")
        ws_id = self.ids.next(ResourceKind.WORKSPACE)
        self.workspaces[ws_id] = Workspace(ws_id, name, domain, created=clock.now_iso())
        return ws_id

    def add_user(self, workspace_id: str, email: str, name: Optional[str] = None) -> str:
        self.get_workspace(workspace_id)
        email = (email or "").strip().lower()
        if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
            raise Invalid(f"bad email {email!r}")
        for u in self.users.values():
            if u.workspace_id == workspace_id and u.email == email:
                raise Invalid(f"{email} is already in this workspace")
        user_id = self.ids.next(ResourceKind.USER)
        display = (name or email.split("@")[0]).strip()
        self.users[user_id] = User(user_id, workspace_id, email, display, created=clock.now_iso())
        return user_id

    def add_admin(self, workspace_id: str, user_id: str) -> None:
        ws = self.get_workspace(workspace_id)
        user = self.get_user(user_id)
        if user.workspace_id != workspace_id:
            raise Invalid(f"{user_id} is not in {workspace_id}")
        if user_id not in ws.admins:
            ws.admins.append(user_id)
            audit.record(self, None, "admin.add", workspace_id, user=user_id)

    def remove_admin(self, workspace_id: str, user_id: str) -> None:
        ws = self.get_workspace(workspace_id)
        if user_id in ws.admins:
            ws.admins.remove(user_id)
            audit.record(self, None, "admin.remove", workspace_id, user=user_id)

    def suspend_user(self, user_id: str) -> None:
        user = self.get_user(user_id)
        user.status = UserStatus.SUSPENDED
        audit.record(self, None, "user.suspend", user_id)

    def reactivate_user(self, user_id: str) -> None:
        user = self.get_user(user_id)
        user.status = UserStatus.ACTIVE
        audit.record(self, None, "user.reactivate", user_id)

    # -- groups ----------------------------------------------------------------

    def add_group(self, workspace_id: str, name: str, members: Iterable[str] = ()) -> str:
        self.get_workspace(workspace_id)
        name = (name or "").strip()
        if not name:
            raise Invalid("group name is empty")
        group_id = self.ids.next(ResourceKind.GROUP)
        self.groups[group_id] = Group(group_id, workspace_id, name, created=clock.now_iso())
        for user_id in members:
            self.add_member(group_id, user_id)
        return group_id

    def add_member(self, group_id: str, user_id: str) -> None:
        group = self.get_group(group_id)
        user = self.get_user(user_id)
        if user.workspace_id != group.workspace_id:
            raise Invalid(f"{user_id} is not in {group.workspace_id}")
        if user_id not in group.members:
            group.members.append(user_id)

    def remove_member(self, group_id: str, user_id: str) -> None:
        group = self.get_group(group_id)
        if user_id in group.members:
            group.members.remove(user_id)

    def add_subgroup(self, group_id: str, child_id: str) -> None:
        """Nest ``child_id`` inside ``group_id``.

        No loop check: the directory sync imports nesting exactly as the
        directory has it, loops included.
        """
        group = self.get_group(group_id)
        child = self.get_group(child_id)
        if child.workspace_id != group.workspace_id:
            raise Invalid("groups are in different workspaces")
        if child_id == group_id:
            raise Invalid("a group can't contain itself")
        if child_id not in group.subgroups:
            group.subgroups.append(child_id)

    def remove_subgroup(self, group_id: str, child_id: str) -> None:
        group = self.get_group(group_id)
        if child_id in group.subgroups:
            group.subgroups.remove(child_id)

    # -- folders ---------------------------------------------------------------

    def create_folder(self, workspace_id: str, name: str, owner_id: str,
                      parent_id: Optional[str] = None) -> str:
        self.get_workspace(workspace_id)
        owner = self.get_user(owner_id)
        if owner.workspace_id != workspace_id:
            raise Invalid(f"{owner_id} is not in {workspace_id}")
        name = (name or "").strip()
        if not name or "/" in name:
            raise Invalid(f"bad folder name {name!r}")
        if parent_id is not None:
            parent = self.get_folder(parent_id)
            if parent.workspace_id != workspace_id:
                raise Invalid("parent folder is in another workspace")
        for f in self.folders.values():
            if f.workspace_id == workspace_id and f.parent_id == parent_id and f.name == name:
                raise Invalid(f"a folder called {name!r} already exists there")
        folder_id = self.ids.next(ResourceKind.FOLDER)
        self.folders[folder_id] = Folder(folder_id, workspace_id, name, owner_id, parent_id,
                                         created=clock.now_iso())
        audit.record(self, owner_id, "folder.create", folder_id, name=name)
        return folder_id

    def move_folder(self, folder_id: str, new_parent_id: Optional[str]) -> None:
        folder = self.get_folder(folder_id)
        cursor = new_parent_id
        while cursor is not None:
            if cursor == folder_id:
                raise Invalid("can't move a folder inside itself")
            cursor = self.get_folder(cursor).parent_id
        if new_parent_id is not None and self.get_folder(new_parent_id).workspace_id != folder.workspace_id:
            raise Invalid("can't move a folder to another workspace")
        folder.parent_id = new_parent_id
        audit.record(self, None, "folder.move", folder_id, parent=new_parent_id)

    # -- documents -------------------------------------------------------------

    def create_document(self, folder_id: str, title: str, owner_id: str, body: str = "") -> str:
        folder = self.get_folder(folder_id)
        owner = self.get_user(owner_id)
        if owner.workspace_id != folder.workspace_id:
            raise Invalid(f"{owner_id} is not in {folder.workspace_id}")
        title = (title or "").strip()
        if not title:
            raise Invalid("document title is empty")
        doc_id = self.ids.next(ResourceKind.DOCUMENT)
        now = clock.now_iso()
        self.documents[doc_id] = Document(doc_id, folder.workspace_id, folder_id, title, owner_id,
                                          body=body, created=now, updated=now)
        self.revisions[doc_id] = [Revision(doc_id, 1, body, owner_id, now)]
        self.comments[doc_id] = []
        audit.record(self, owner_id, "document.create", doc_id, title=title)
        return doc_id

    def move_document(self, doc_id: str, folder_id: str) -> None:
        doc = self.get_document(doc_id)
        folder = self.get_folder(folder_id)
        if folder.workspace_id != doc.workspace_id:
            raise Invalid("can't move a document to another workspace")
        doc.folder_id = folder_id
        audit.record(self, None, "document.move", doc_id, folder=folder_id)

    def set_restricted(self, doc_id: str, restricted: bool = True) -> None:
        doc = self.get_document(doc_id)
        doc.restricted = bool(restricted)
        audit.record(self, None, "document.restrict" if restricted else "document.unrestrict", doc_id)

    def trash_document(self, doc_id: str) -> None:
        doc = self.get_document(doc_id)
        if not doc.trashed:
            doc.trashed = True
            doc.trashed_at = clock.now_iso()
            audit.record(self, None, "document.trash", doc_id)

    def restore_document(self, doc_id: str) -> None:
        doc = self.get_document(doc_id)
        if doc.trashed:
            doc.trashed = False
            doc.trashed_at = None
            audit.record(self, None, "document.restore", doc_id)

    def next_comment_id(self) -> str:
        self._comment_seq += 1
        return f"cmt_{self._comment_seq:04d}"

    # -- iteration helpers -----------------------------------------------------

    def documents_in_workspace(self, workspace_id: str, include_trashed: bool = False) -> list[Document]:
        return [d for d in self.documents.values()
                if d.workspace_id == workspace_id and (include_trashed or not d.trashed)]

    def groups_in_workspace(self, workspace_id: str) -> list[Group]:
        return [g for g in self.groups.values() if g.workspace_id == workspace_id]

    def users_in_workspace(self, workspace_id: str) -> list[User]:
        return [u for u in self.users.values() if u.workspace_id == workspace_id]
