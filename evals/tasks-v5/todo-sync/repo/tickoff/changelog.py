"""The per-replica change log.

Every local change to a task appends one Change: which device made it, the
Lamport counter and wall time it got, the task, the kind of change and the
fields it set. Nothing reads the log back into tasks yet; it is there for
history (`tickoff history`) and for sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field

KINDS = ("create", "update", "delete")


@dataclass(frozen=True)
class Change:
    device: str
    lamport: int
    wall: str
    task_id: str
    kind: str
    fields: dict = field(default_factory=dict)
    # `wall` is what tells us which edit is newest when two devices touch
    # the same task. `lamport` is only kept so one device's entries stay in
    # order in the file.

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown change kind: {self.kind}")

    @property
    def op_id(self) -> str:
        """Unique per change: a device never reuses a counter value."""
        return f"{self.device}:{self.lamport}"

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "lamport": self.lamport,
            "wall": self.wall,
            "task": self.task_id,
            "kind": self.kind,
            "fields": dict(self.fields),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Change":
        return cls(
            device=data["device"],
            lamport=int(data["lamport"]),
            wall=data["wall"],
            task_id=data["task"],
            kind=data["kind"],
            fields=dict(data.get("fields") or {}),
        )

    def summary(self) -> str:
        if self.kind == "create":
            what = f"created {self.fields.get('title', '')!r}"
        elif self.kind == "delete":
            what = "deleted"
        else:
            what = ", ".join(f"{k}={v!r}" for k, v in sorted(self.fields.items()))
        return f"{self.wall} {self.device} #{self.lamport} {what}"


class ChangeLog:
    def __init__(self, entries=()):
        self._entries: list[Change] = list(entries)

    def append(self, change: Change) -> None:
        self._entries.append(change)

    def __iter__(self):
        return iter(self._entries)

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, index):
        return self._entries[index]

    def last(self) -> Change | None:
        return self._entries[-1] if self._entries else None

    def since(self, lamport: int) -> list[Change]:
        """Entries with a counter above `lamport`."""
        return [c for c in self._entries if c.lamport > lamport]

    def for_task(self, task_id: str) -> list[Change]:
        return [c for c in self._entries if c.task_id == task_id]

    def history(self, task_id: str) -> list[str]:
        return [c.summary() for c in self.for_task(task_id)]

    def to_list(self) -> list[dict]:
        return [c.to_dict() for c in self._entries]

    @classmethod
    def from_list(cls, items) -> "ChangeLog":
        return cls(Change.from_dict(item) for item in items or [])

    def trim_before(self, wall: str) -> int:
        """Drop entries older than `wall`. Used by the 0.3 compaction job,
        which has since been removed."""
        before = len(self._entries)
        self._entries = [c for c in self._entries if c.wall >= wall]
        return before - len(self._entries)
