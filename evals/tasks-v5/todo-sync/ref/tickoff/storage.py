"""Reading and writing replica files.

A replica file is JSON:

    {
      "format": 2,
      "device": "laptop",
      "lamport": 41,
      "tasks": [ {task}, ... ],
      "log": [ {change}, ... ],
      "sync": { ... }
    }

Format 1 (tickoff 0.2) had "items" with "name" and "position" instead of
"tasks" with "title" and "order", and no log. It is upgraded on load.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .changelog import ChangeLog
from .clock import LamportClock
from .models import Task

FORMAT = 2


class StorageError(Exception):
    pass


def replica_to_dict(replica) -> dict:
    return {
        "format": FORMAT,
        "device": replica.device_id,
        "lamport": replica.clock.value,
        "tasks": [t.to_dict() for t in sorted(replica.tasks.values(), key=lambda t: t.id)],
        "log": replica.log.to_list(),
        "sync": replica.sync_state,
        "meta": replica.meta,
        "tombstones": [t.to_dict() for t in sorted(replica.tombstones.values(), key=lambda t: t.id)],
    }


def replica_from_dict(data: dict, *, wall=None, path=None):
    from .replica import Replica

    data = upgrade(data)
    replica = Replica(data["device"], wall=wall, clock=LamportClock(data.get("lamport", 0)), path=path)
    for item in data.get("tasks", []):
        task = Task.from_dict(item)
        replica.tasks[task.id] = task
    replica.log = ChangeLog.from_list(data.get("log", []))
    replica.sync_state = dict(data.get("sync") or {})
    replica.meta = {tid: {"fields": dict(m.get("fields") or {}), "deleted": m.get("deleted")}
                    for tid, m in (data.get("meta") or {}).items()}
    for item in data.get("tombstones", []):
        task = Task.from_dict(item)
        replica.tombstones[task.id] = task
    return replica


def upgrade(data: dict) -> dict:
    version = data.get("format", 1)
    if version > FORMAT:
        raise StorageError(f"replica format {version} is newer than this tickoff ({FORMAT})")
    if version == 1:
        tasks = []
        for item in data.get("items", []):
            tasks.append({
                "id": item["id"],
                "title": item["name"],
                "list": item.get("list", "inbox"),
                "done": bool(item.get("done", False)),
                "due": item.get("due"),
                "order": item.get("position", 0),
                "created_by": data["device"],
            })
        data = {"format": FORMAT, "device": data["device"], "lamport": 0,
                "tasks": tasks, "log": [], "sync": {}}
    return data


def load_replica(path, *, wall=None):
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise StorageError(f"no replica at {path}") from None
    except json.JSONDecodeError as exc:
        raise StorageError(f"{path} is not valid JSON: {exc}") from None
    return replica_from_dict(data, wall=wall, path=path)


def save_replica(replica, path) -> None:
    if path is None:
        raise StorageError("replica has no path; pass one to save()")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(replica_to_dict(replica), indent=2, sort_keys=True)
    # Write to a temp file and rename, so a crash never leaves half a file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    replica.path = path


def default_path(device_id: str) -> Path:
    home = Path(os.environ.get("TICKOFF_HOME", Path.home() / ".tickoff"))
    return home / f"{device_id}.json"
