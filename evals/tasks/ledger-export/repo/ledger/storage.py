"""JSON file storage for entries.

The file is ``entries.json`` in the ledger home directory::

    {"version": 1, "entries": [{"id": 1, "ts": "2026-03-01T14:05:00Z", ...}]}
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from ledger.models import Entry
from ledger.settings import ledger_home

FILE_VERSION = 1


def entries_path() -> Path:
    return ledger_home() / "entries.json"


def load_entries() -> List[Entry]:
    path = entries_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("version") != FILE_VERSION:
        raise ValueError(f"unsupported ledger file version: {data.get('version')}")
    entries = [Entry.from_dict(item) for item in data.get("entries", [])]
    entries.sort(key=lambda e: (e.ts, e.id))
    return entries


def save_entries(entries: List[Entry]) -> None:
    path = entries_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": FILE_VERSION, "entries": [e.to_dict() for e in entries]}
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def next_id(entries: List[Entry]) -> int:
    return max((e.id for e in entries), default=0) + 1


def find_entry(entries: List[Entry], entry_id: int) -> Optional[Entry]:
    for entry in entries:
        if entry.id == entry_id:
            return entry
    return None
