"""Sync a replica with the hub: pull other devices' changes, apply them
(newest edit wins), then push ours."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Task


@dataclass
class SyncReport:
    pushed: int = 0
    pulled: int = 0


def sync(replica, hub) -> SyncReport:
    incoming, cursor = hub.pull(replica.device_id, replica.sync_state.get("cursor", 0))
    for change in sorted(incoming, key=lambda c: c.wall):
        _apply(replica, change)
    replica.sync_state["cursor"] = cursor

    start = replica.sync_state.get("pushed", 0)
    outgoing = list(replica.log)[start:]
    hub.push(replica.device_id, outgoing)
    replica.sync_state["pushed"] = len(replica.log)
    return SyncReport(pushed=len(outgoing), pulled=len(incoming))


def _apply(replica, change) -> None:
    task = replica.tasks.get(change.task_id)
    if change.kind == "create":
        if task is None:
            replica.tasks[change.task_id] = Task.from_dict({
                **change.fields, "id": change.task_id, "created_by": change.device,
                "created_at": change.wall, "updated_at": change.wall})
        return
    if task is None:
        return  # deleted here, or never seen
    if change.wall < task.updated_at:
        return  # we have a newer edit; keep the newest
    if change.kind == "delete":
        del replica.tasks[change.task_id]
        return
    for name, value in change.fields.items():
        setattr(task, name, value)
    task.updated_at = change.wall
