"""A tiny JSON-file store.

Each table is one JSON file (a list of row dicts) inside the data directory.
Writes go to a temp file and are renamed into place so a crash never leaves a
half-written table behind. There is no locking: the CLI is single-user.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from payouts import config
from payouts.errors import NotFound

COUNTERS = "_counters"


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else config.data_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- raw table access -------------------------------------------------

    def _path(self, table: str) -> Path:
        if not table.replace("_", "").isalnum():
            raise ValueError(f"bad table name: {table!r}")
        return self.root / f"{table}.json"

    def load(self, table: str) -> list[dict[str, Any]]:
        path = self._path(table)
        if not path.exists():
            return []
        with path.open() as fh:
            return json.load(fh)

    def save(self, table: str, rows: list[dict[str, Any]]) -> None:
        path = self._path(table)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{table}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(rows, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def load_doc(self, name: str) -> dict[str, Any]:
        """Load a table that holds a single dict instead of a list of rows."""
        path = self._path(name)
        if not path.exists():
            return {}
        with path.open() as fh:
            return json.load(fh)

    def save_doc(self, name: str, doc: dict[str, Any]) -> None:
        self.save(name, doc)  # type: ignore[arg-type]

    # -- row helpers ------------------------------------------------------

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        rows = self.load(table)
        if any(r.get("id") == row.get("id") for r in rows):
            raise ValueError(f"duplicate id in {table}: {row.get('id')}")
        rows.append(row)
        self.save(table, rows)
        return row

    def get(self, table: str, row_id: str) -> dict[str, Any]:
        for row in self.load(table):
            if row.get("id") == row_id:
                return row
        raise NotFound(f"no {table[:-1] if table.endswith('s') else table} with id {row_id}")

    def find(self, table: str, pred: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        return [row for row in self.load(table) if pred(row)]

    def update(self, table: str, row_id: str, **changes: Any) -> dict[str, Any]:
        rows = self.load(table)
        for row in rows:
            if row.get("id") == row_id:
                row.update(changes)
                self.save(table, rows)
                return row
        raise NotFound(f"no row {row_id} in {table}")

    # -- ids --------------------------------------------------------------

    def next_id(self, prefix: str) -> str:
        """Sequential ids per prefix: m_0001, ch_0001, ch_0002, ..."""
        counters = self.load_doc(COUNTERS)
        n = int(counters.get(prefix, 0)) + 1
        counters[prefix] = n
        self.save_doc(COUNTERS, counters)
        return f"{prefix}_{n:04d}"
