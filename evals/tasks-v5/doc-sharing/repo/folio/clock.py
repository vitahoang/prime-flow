"""Time source. Tests and the CLI can pin it with $FOLIO_NOW."""

from __future__ import annotations

import os
from datetime import datetime, timezone


def now() -> datetime:
    pinned = os.environ.get("FOLIO_NOW")
    if pinned:
        return datetime.fromisoformat(pinned)
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now().isoformat()
