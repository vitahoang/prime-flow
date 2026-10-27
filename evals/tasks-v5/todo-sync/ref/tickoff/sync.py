"""Sync a replica with the hub.

    report = sync(replica, hub)

1. Pull everything other devices stored since our last pull and merge it
   (Replica.merge: per field, the later change by Lamport counter then device
   id wins; a delete hides a task unless a field was changed after it).
2. Push our own changes the hub doesn't have yet. The hub's head(device)
   says how far it got, so a push cut off by a dropped connection is resumed,
   not repeated, on the next sync.

Two things never leave a device:
- anything in the `work` list (it stays on the device it's on);
- on the kitchen `fridge` tablet, anything except ticking tasks off or on.

Running sync again with nothing new does nothing.
"""

from __future__ import annotations

from dataclasses import dataclass


LOCAL_ONLY_LIST = "work"
DISPLAY_DEVICE = "fridge"


@dataclass
class SyncReport:
    pushed: int = 0      # our changes sent to the hub
    pulled: int = 0      # other devices' changes received
    applied: int = 0     # received changes that changed something here


def sync(replica, hub) -> SyncReport:
    report = SyncReport()

    incoming, cursor = hub.pull(replica.device_id, replica.sync_state.get("pulled_to", 0))
    for change in incoming:
        if replica.merge(change):
            report.applied += 1
    report.pulled = len(incoming)
    replica.sync_state["pulled_to"] = cursor

    have = hub.head(replica.device_id)
    outgoing = sorted((c for c in replica.log if c.device == replica.device_id and c.lamport > have
                       and _may_leave(replica, c)), key=lambda c: c.lamport)
    hub.push(replica.device_id, outgoing)  # may raise NetworkDropped; the next sync resumes
    report.pushed = len(outgoing)
    return report


def _may_leave(replica, change) -> bool:
    if _in_work_list(replica, change):
        return False
    if replica.device_id == DISPLAY_DEVICE:
        return _only_ticks(change)
    return True


def _in_work_list(replica, change) -> bool:
    task = replica.tasks.get(change.task_id) or replica.tombstones.get(change.task_id)
    current = task.list if task else None
    return LOCAL_ONLY_LIST in (current, change.fields.get("list"))


def _only_ticks(change) -> bool:
    return change.kind == "update" and set(change.fields) == {"done"}
