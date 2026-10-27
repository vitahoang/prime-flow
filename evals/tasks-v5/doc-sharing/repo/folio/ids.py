"""Id generation.

Ids are a kind prefix plus a zero-padded counter: ``doc_0003``. The prefix is
how the store tells what kind of thing an id refers to (store.kind_of).
"""

from __future__ import annotations

import itertools
import re

from .models import ResourceKind

PREFIXES = {
    ResourceKind.WORKSPACE: "ws",
    ResourceKind.FOLDER: "fld",
    ResourceKind.DOCUMENT: "doc",
    ResourceKind.USER: "usr",
    ResourceKind.GROUP: "grp",
}
_BY_PREFIX = {v: k for k, v in PREFIXES.items()}
_ID_RE = re.compile(r"^([a-z]+)_(\d+)$")


class IdSource:
    def __init__(self, start: int = 1):
        self._counters = {kind: itertools.count(start) for kind in PREFIXES}

    def next(self, kind: ResourceKind) -> str:
        return f"{PREFIXES[kind]}_{next(self._counters[kind]):04d}"

    def bump_past(self, ident: str) -> None:
        """Make sure later ids don't collide with one loaded from disk."""
        m = _ID_RE.match(ident)
        if not m or m.group(1) not in _BY_PREFIX:
            return
        kind = _BY_PREFIX[m.group(1)]
        n = int(m.group(2))
        current = next(self._counters[kind])
        self._counters[kind] = itertools.count(max(current, n + 1))


def kind_of(ident: str) -> ResourceKind | None:
    m = _ID_RE.match(ident or "")
    if not m:
        return None
    return _BY_PREFIX.get(m.group(1))
