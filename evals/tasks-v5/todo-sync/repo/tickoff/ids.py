"""Task ids.

Ids are random so two devices can create tasks offline without clashing.
"""

import re
import secrets

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
DEVICE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def new_id() -> str:
    """A random 12 hex digit id."""
    return secrets.token_hex(6)


def short(task_id: str) -> str:
    """The prefix the CLI shows."""
    return task_id[:6]


def check_task_id(task_id: str) -> str:
    if not isinstance(task_id, str) or not ID_RE.match(task_id):
        raise ValueError(f"bad task id: {task_id!r}")
    return task_id


def check_device_id(device_id: str) -> str:
    if not isinstance(device_id, str) or not DEVICE_RE.match(device_id):
        raise ValueError(f"bad device id: {device_id!r} (lowercase letters, digits, '-')")
    return device_id
