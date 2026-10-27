"""Today's date, overridable for tests and for re-running old reports.

Set ``STOCKROOM_TODAY=YYYY-MM-DD`` to pretend it is another day.
"""

from __future__ import annotations

import os
from datetime import date

ENV_VAR = "STOCKROOM_TODAY"


def today() -> date:
    override = os.environ.get(ENV_VAR, "").strip()
    if override:
        return date.fromisoformat(override)
    return date.today()
