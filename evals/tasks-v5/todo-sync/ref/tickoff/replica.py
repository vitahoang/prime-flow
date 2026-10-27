"""A replica: one device's copy of the tasks, plus its change log.

All changes go through the methods here so that each one is logged with the
device id, a Lamport counter and the device's wall time.
"""

from __future__ import annotations

from .changelog import Change, ChangeLog
from .clock import LamportClock, SystemWall
from .ids import check_device_id, check_task_id, new_id
from .models import DEFAULT_LIST, Task, clean_list_name, validate_fields


def stamp(change: Change) -> tuple:
    """Which of two changes counts as later: the Lamport counter, then the
    device id. Wall time never decides (device clocks drift)."""
    return (change.lamport, change.device)


class Replica:
    def __init__(self, device_id: str, *, wall=None, clock: LamportClock | None = None, path=None):
        self.device_id = check_device_id(device_id)
        self.wall = wall or SystemWall()
        self.clock = clock or LamportClock()
        self.tasks: dict[str, Task] = {}
        self.log = ChangeLog()
        # Free-form bookkeeping, saved with the replica. Reserved for sync.
        self.sync_state: dict = {}
        self.path = path
        # Merge bookkeeping, per task id:
        #   {"fields": {field: [lamport, device]}, "deleted": [lamport, device] | None}
        self.meta: dict[str, dict] = {}
        # Deleted tasks, kept so that a later edit from another device can
        # bring them back with their other fields intact.
        self.tombstones: dict[str, Task] = {}

    # ---- reading -------------------------------------------------------

    def get(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def require(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(f"no such task: {task_id}")
        return task

    def find(self, ref: str) -> Task:
        """Look a task up by id, id prefix or exact title (for the CLI)."""
        if ref in self.tasks:
            return self.tasks[ref]
        by_prefix = [t for t in self.tasks.values() if t.id.startswith(ref)]
        if len(by_prefix) == 1:
            return by_prefix[0]
        by_title = [t for t in self.tasks.values() if t.title.lower() == ref.lower()]
        if len(by_title) == 1:
            return by_title[0]
        if len(by_prefix) + len(by_title) > 1:
            raise KeyError(f"{ref!r} matches more than one task")
        raise KeyError(f"no such task: {ref}")

    def all_tasks(self) -> list[Task]:
        return [t for name in self.lists() for t in self.list_tasks(name)]

    def lists(self) -> list[str]:
        """List names in use, inbox first, then alphabetical."""
        names = {t.list for t in self.tasks.values()}
        return sorted(names, key=lambda n: (n != DEFAULT_LIST, n))

    def list_tasks(self, list_name: str = DEFAULT_LIST, *, include_done: bool = True) -> list[Task]:
        """The tasks in one list, in their order."""
        tasks = [t for t in self.tasks.values()
                 if t.list == list_name and (include_done or not t.done)]
        return sorted(tasks, key=self._sort_key)

    def _sort_key(self, task: Task):
        return (task.order, self._order_device(task.id), task.id)

    def _order_device(self, task_id: str) -> str:
        """The device that set this task's order. Breaks ties between tasks
        two devices put at the same spot."""
        st = self.meta.get(task_id, {}).get("fields", {}).get("order")
        return st[1] if st else ""

    # ---- writing -------------------------------------------------------

    def add_task(self, title, *, list: str = DEFAULT_LIST, due=None, position=None,
                 task_id: str | None = None) -> Task:
        """Create a task. `position` is an index into the list (None = end)."""
        values = validate_fields({"title": title, "list": list, "due": due})
        tid = check_task_id(task_id) if task_id else new_id()
        if tid in self.tasks:
            raise ValueError(f"task {tid} already exists")
        order = self._place(values["list"], position)
        now = self.wall.now()
        task = Task(id=tid, title=values["title"], list=values["list"], due=values["due"],
                    order=order, created_by=self.device_id, created_at=now, updated_at=now)
        self.tasks[tid] = task
        self._record("create", tid, task.fields())
        return task

    def edit_task(self, task_id: str, **changes) -> Task:
        task = self.require(task_id)
        changes = validate_fields(changes)
        if "list" in changes and changes["list"] != task.list and "order" not in changes:
            changes["order"] = self._place(changes["list"], None)
        changed = {k: v for k, v in changes.items() if getattr(task, k) != v}
        if not changed:
            return task
        for name, value in changed.items():
            setattr(task, name, value)
        self._record("update", task_id, changed)
        return task

    def complete(self, task_id: str) -> Task:
        return self.edit_task(task_id, done=True)

    def reopen(self, task_id: str) -> Task:
        return self.edit_task(task_id, done=False)

    def rename(self, task_id: str, title) -> Task:
        return self.edit_task(task_id, title=title)

    def set_due(self, task_id: str, due) -> Task:
        return self.edit_task(task_id, due=due)

    def delete_task(self, task_id: str) -> None:
        self.require(task_id)
        self._record("delete", task_id, {})

    def move_task(self, task_id: str, position: int, *, list: str | None = None) -> Task:
        """Move a task to `position` in its list, or in `list` if given."""
        task = self.require(task_id)
        target = clean_list_name(list) if list else task.list
        changes = {"order": self._place(target, position, exclude=task_id)}
        if target != task.list:
            changes["list"] = target
        for name, value in changes.items():
            setattr(task, name, value)
        self._record("update", task_id, changes)
        return task

    def _place(self, list_name: str, position, exclude: str | None = None) -> float:
        """The order value for a task going to `position` in `list_name`.

        Only the moving task gets a new value (between its new neighbours);
        other tasks are never renumbered, so their order can't clash with
        another device's moves.
        """
        seq = [t for t in self.list_tasks(list_name) if t.id != exclude]
        if position is None or position >= len(seq):
            return (seq[-1].order + 1) if seq else 1
        if position <= 0:
            return seq[0].order - 1
        return (seq[position - 1].order + seq[position].order) / 2

    def compact_orders(self, list_name: str) -> None:
        """Renumber a list 1..n. Was run after legacy imports."""
        for i, task in enumerate(self.list_tasks(list_name), start=1):
            if task.order != i:
                task.order = i
                self._record("update", task.id, {"order": i})

    def _record(self, kind: str, task_id: str, fields: dict) -> Change:
        change = Change(device=self.device_id, lamport=self.clock.tick(), wall=self.wall.now(),
                        task_id=task_id, kind=kind, fields=dict(fields))
        self.log.append(change)
        task = self.tasks.get(task_id)
        if task is not None:
            task.updated_at = change.wall
        meta = self._meta(task_id)
        if kind == "delete":
            meta["deleted"] = list(stamp(change))
        for name in fields:
            meta["fields"][name] = list(stamp(change))
        self._settle(task_id)
        return change

    # ---- merging other devices' changes ----------------------------------

    def _meta(self, task_id: str) -> dict:
        return self.meta.setdefault(task_id, {"fields": {}, "deleted": None})

    def merge(self, change: Change) -> bool:
        """Apply a change made on another device. Field by field, the later
        change (by stamp()) wins. Applying a change twice does nothing.
        Returns True if anything changed here."""
        self.clock.observe(change.lamport)
        tid = change.task_id
        meta = self._meta(tid)
        new = stamp(change)
        task = self.tasks.get(tid) or self.tombstones.get(tid)
        changed = False
        if task is None:
            task = Task(id=tid, title="", created_by=change.device,
                        created_at=change.wall, updated_at=change.wall)
            self.tombstones[tid] = task
        if change.kind == "delete":
            if meta["deleted"] is None or new > tuple(meta["deleted"]):
                meta["deleted"] = list(new)
                changed = True
        else:
            for name, value in change.fields.items():
                cur = meta["fields"].get(name)
                if cur is None or new > tuple(cur):
                    setattr(task, name, value)
                    meta["fields"][name] = list(new)
                    changed = True
            if changed:
                task.updated_at = change.wall
        self._settle(tid)
        return changed

    def _alive(self, task_id: str) -> bool:
        """A delete hides a task unless some field was changed after it."""
        meta = self.meta.get(task_id)
        if not meta or meta["deleted"] is None:
            return True
        latest = max((tuple(s) for s in meta["fields"].values()), default=None)
        return latest is not None and latest > tuple(meta["deleted"])

    def _settle(self, task_id: str) -> None:
        if self._alive(task_id):
            if task_id in self.tombstones:
                self.tasks[task_id] = self.tombstones.pop(task_id)
        elif task_id in self.tasks:
            self.tombstones[task_id] = self.tasks.pop(task_id)

    # ---- files ---------------------------------------------------------

    @classmethod
    def load(cls, path, *, wall=None) -> "Replica":
        from .storage import load_replica
        return load_replica(path, wall=wall)

    def save(self, path=None) -> None:
        from .storage import save_replica
        save_replica(self, path or self.path)
