"""Group helpers."""

from __future__ import annotations

from typing import Iterator


def direct_members(store, group_id: str) -> list[str]:
    """User ids listed on the group itself (not its subgroups)."""
    return list(store.get_group(group_id).members)


def groups_listing(store, user_id: str) -> list[str]:
    """Ids of the groups that list ``user_id`` directly, in creation order."""
    return [g.id for g in store.groups.values() if user_id in g.members]


def group_tree(store, group_id: str, max_depth: int = 6) -> Iterator[str]:
    """Indented lines for ``folio groups``: the group, its people, its subgroups,
    down to ``max_depth`` levels."""

    def walk(gid: str, depth: int) -> Iterator[str]:
        group = store.get_group(gid)
        pad = "  " * depth
        yield f"{pad}{group.name} ({gid})"
        for uid in group.members:
            yield f"{pad}  - {store.get_user(uid).name}"
        if depth >= max_depth:
            if group.subgroups:
                yield f"{pad}  ..."
            return
        for child in group.subgroups:
            yield from walk(child, depth + 1)

    yield from walk(group_id, 0)


def rename(store, group_id: str, name: str) -> None:
    name = (name or "").strip()
    if name:
        store.get_group(group_id).name = name
