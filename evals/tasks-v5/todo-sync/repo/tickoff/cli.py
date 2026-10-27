"""`python -m tickoff` — a small command line front end.

The replica file is $TICKOFF_HOME/<device>.json; the device id comes from
--device or $TICKOFF_DEVICE.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from . import export, lists, query
from .due import DueParseError, describe, parse_due
from .ids import short
from .models import DEFAULT_LIST, ValidationError
from .replica import Replica
from .storage import StorageError, default_path


def _today() -> date:
    override = os.environ.get("TICKOFF_TODAY")
    return date.fromisoformat(override) if override else date.today()


def open_replica(device: str) -> Replica:
    path = default_path(device)
    if path.exists():
        return Replica.load(path)
    return Replica(device, path=path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tickoff")
    p.add_argument("--device", default=os.environ.get("TICKOFF_DEVICE", "laptop"))
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title", nargs="+")
    a.add_argument("--list", default=DEFAULT_LIST)
    a.add_argument("--due")
    a.add_argument("--at", type=int, help="position in the list (0 = top)")

    ls = sub.add_parser("ls", help="show tasks")
    ls.add_argument("list", nargs="?")
    ls.add_argument("--all", action="store_true", help="include finished tasks")

    for name in ("done", "undo", "rm", "history"):
        c = sub.add_parser(name)
        c.add_argument("task")

    mv = sub.add_parser("mv", help="move a task")
    mv.add_argument("task")
    mv.add_argument("position", type=int)
    mv.add_argument("--list")

    e = sub.add_parser("edit")
    e.add_argument("task")
    e.add_argument("--title")
    e.add_argument("--due")

    sub.add_parser("agenda")
    sub.add_parser("export")
    rl = sub.add_parser("rename-list")
    rl.add_argument("old")
    rl.add_argument("new")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        replica = open_replica(args.device)
        changed = _dispatch(replica, args)
        if changed:
            replica.save()
    except (KeyError, ValidationError, DueParseError, StorageError, ValueError) as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(f"tickoff: {msg}", file=sys.stderr)
        return 1
    return 0


def _dispatch(replica: Replica, args) -> bool:
    today = _today()
    if args.cmd == "add":
        due = parse_due(args.due, today) if args.due else None
        task = replica.add_task(" ".join(args.title), list=args.list, due=due, position=args.at)
        print(f"added {short(task.id)} {task.title}")
        return True
    if args.cmd == "ls":
        names = [args.list] if args.list else replica.lists()
        for name in names:
            tasks = replica.list_tasks(name, include_done=args.all)
            if not tasks:
                continue
            print(f"{name}:")
            for task in tasks:
                box = "x" if task.done else " "
                when = describe(task.due, today)
                print(f"  [{box}] {short(task.id)} {task.title}" + (f"  ({when})" if when else ""))
        return False
    if args.cmd in ("done", "undo", "rm", "history"):
        task = replica.find(args.task)
        if args.cmd == "done":
            replica.complete(task.id)
        elif args.cmd == "undo":
            replica.reopen(task.id)
        elif args.cmd == "rm":
            replica.delete_task(task.id)
        else:
            for line in replica.log.history(task.id):
                print(line)
            return False
        return True
    if args.cmd == "mv":
        replica.move_task(replica.find(args.task).id, args.position, list=args.list)
        return True
    if args.cmd == "edit":
        task = replica.find(args.task)
        changes = {}
        if args.title:
            changes["title"] = args.title
        if args.due is not None:
            changes["due"] = parse_due(args.due, today)
        replica.edit_task(task.id, **changes)
        return True
    if args.cmd == "agenda":
        for label, tasks in query.agenda(replica, today):
            print(f"{label}:")
            for task in tasks:
                print(f"  {task.title} [{task.list}]")
        return False
    if args.cmd == "export":
        sys.stdout.write(export.to_markdown(replica, today))
        return False
    if args.cmd == "rename-list":
        n = lists.rename_list(replica, args.old, args.new)
        print(f"moved {n} task(s)")
        return True
    raise ValueError(f"unknown command {args.cmd}")
