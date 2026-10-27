"""Where pennywise keeps its data, and what "today" is.

The database path comes from ``--db``, then ``$PENNYWISE_DB``, then
``~/.pennywise/pennywise.db``. ``$PENNYWISE_TODAY`` (YYYY-MM-DD) pins today's
date, which the tests and the demo script use.
"""

import os
from datetime import date
from pathlib import Path

DEFAULT_DB = Path.home() / ".pennywise" / "pennywise.db"

# Currency used when an account is created without one.
DEFAULT_CURRENCY = "GBP"


def db_path(cli_value=None):
    if cli_value:
        return Path(cli_value)
    env = os.environ.get("PENNYWISE_DB")
    if env:
        return Path(env)
    return DEFAULT_DB


def today():
    pinned = os.environ.get("PENNYWISE_TODAY")
    if pinned:
        return date.fromisoformat(pinned)
    return date.today()
