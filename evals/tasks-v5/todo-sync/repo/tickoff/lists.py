"""Operations on whole lists. Each one is a series of ordinary task changes,
so it shows up in the change log like anything else."""

from __future__ import annotations

from .models import DEFAULT_LIST, clean_list_name


def rename_list(replica, old: str, new: str) -> int:
    """Move every task from `old` to `new`, keeping their order. Returns how
    many tasks moved."""
    old, new = clean_list_name(old), clean_list_name(new)
    if old == new:
        return 0
    moved = 0
    for task in replica.list_tasks(old):
        replica.move_task(task.id, None, list=new)
        moved += 1
    return moved


def clear_done(replica, list_name: str) -> int:
    """Delete the finished tasks in a list."""
    done = [t for t in replica.list_tasks(list_name) if t.done]
    for task in done:
        replica.delete_task(task.id)
    return len(done)


def archive_list(replica, list_name: str, archive: str = "archive") -> int:
    if clean_list_name(list_name) == DEFAULT_LIST:
        raise ValueError("the inbox can't be archived")
    return rename_list(replica, list_name, archive)


def reverse_list(replica, list_name: str) -> None:
    tasks = replica.list_tasks(list_name)
    for i, task in enumerate(reversed(tasks)):
        replica.move_task(task.id, i)
