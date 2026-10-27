"""Core records for folio.

Everything is a plain dataclass. The Store (store.py) owns them and hands out
ids; nothing here talks to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ResourceKind(str, Enum):
    WORKSPACE = "workspace"
    FOLDER = "folder"
    DOCUMENT = "document"
    USER = "user"
    GROUP = "group"


@dataclass
class Workspace:
    id: str
    name: str
    # Email domain of staff accounts, e.g. "hollisgrey.com". Accounts on any
    # other domain are guests (see users.is_external).
    domain: str
    # Workspace admins manage people and groups; see store.add_admin.
    admins: list[str] = field(default_factory=list)
    created: str = ""

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.admins


@dataclass
class User:
    id: str
    workspace_id: str
    email: str
    name: str
    status: UserStatus = UserStatus.ACTIVE
    created: str = ""

    @property
    def domain(self) -> str:
        return self.email.rsplit("@", 1)[-1].strip().lower()

    @property
    def active(self) -> bool:
        return self.status is UserStatus.ACTIVE


@dataclass
class Group:
    id: str
    workspace_id: str
    name: str
    members: list[str] = field(default_factory=list)  # user ids
    # Group ids nested inside this one. Everyone in a subgroup is in this group.
    subgroups: list[str] = field(default_factory=list)
    created: str = ""


@dataclass
class Folder:
    id: str
    workspace_id: str
    name: str
    owner_id: str
    parent_id: Optional[str] = None  # None for a top-level folder
    created: str = ""


@dataclass
class Document:
    id: str
    workspace_id: str
    folder_id: str
    title: str
    owner_id: str
    body: str = ""
    # Set by the v1 importer for documents that were "private" in v1.
    restricted: bool = False
    trashed: bool = False
    trashed_at: Optional[str] = None
    revision: int = 1
    created: str = ""
    updated: str = ""


@dataclass
class Comment:
    id: str
    document_id: str
    author_id: str
    text: str
    created: str = ""
    resolved: bool = False


@dataclass
class Revision:
    document_id: str
    number: int
    body: str
    author_id: str
    created: str = ""


@dataclass
class Event:
    """One line of the audit trail (audit.py)."""

    at: str
    actor_id: Optional[str]
    action: str
    resource_id: str
    detail: dict = field(default_factory=dict)
