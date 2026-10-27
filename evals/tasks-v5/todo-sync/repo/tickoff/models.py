"""The Task model and field validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import fields as dc_fields
from datetime import date

# Fields that Replica.edit_task accepts. `order` and `list` also have their
# own entry point, Replica.move_task.
EDITABLE = ("title", "done", "due", "list", "order")
DEFAULT_LIST = "inbox"
MAX_TITLE = 200


class ValidationError(ValueError):
    """A field value that tickoff won't store."""


@dataclass
class Task:
    id: str
    title: str
    list: str = DEFAULT_LIST
    done: bool = False
    due: str | None = None      # ISO date, e.g. "2026-11-03"
    order: float = 0            # position within its list; lower comes first
    created_by: str = ""        # device id
    created_at: str = ""        # wall time on the creating device
    updated_at: str = ""        # wall time of the last change on this device

    def fields(self) -> dict:
        """The editable fields as a dict."""
        return {name: getattr(self, name) for name in EDITABLE}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        known = {f.name for f in dc_fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def is_overdue(self, today: str) -> bool:
        return bool(self.due) and not self.done and self.due < today

    def is_due_on(self, day: str) -> bool:
        return self.due == day


def clean_title(title) -> str:
    text = " ".join(str(title).split())
    if not text:
        raise ValidationError("title is empty")
    if len(text) > MAX_TITLE:
        raise ValidationError(f"title is longer than {MAX_TITLE} characters")
    return text


def clean_list_name(name) -> str:
    text = str(name).strip().lower()
    if not text:
        raise ValidationError("list name is empty")
    if any(ch in text for ch in "/\\:"):
        raise ValidationError(f"list name can't contain / \\ or : ({name!r})")
    return text


def check_due(value):
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(f"due must be an ISO date (YYYY-MM-DD), got {value!r}") from None
    return value


def validate_fields(changes: dict) -> dict:
    """Check and normalise a dict of field changes."""
    out = {}
    for name, value in changes.items():
        if name not in EDITABLE:
            raise ValidationError(f"unknown field: {name}")
        if name == "title":
            value = clean_title(value)
        elif name == "done":
            if not isinstance(value, bool):
                raise ValidationError("done must be true or false")
        elif name == "due":
            value = check_due(value)
        elif name == "list":
            value = clean_list_name(value)
        elif name == "order":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError("order must be a number")
        out[name] = value
    return out
