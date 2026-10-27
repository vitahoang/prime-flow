"""Where the data lives.

Order of precedence: ``--data DIR`` on the command line, then the
``STOCKROOM_DATA`` environment variable, then ``./data``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ENV_VAR = "STOCKROOM_DATA"
DEFAULT_DIR = "data"

# Shops are listed in this order in reports when no other order is asked for.
# Kept here rather than in shops.json because the accountant's spreadsheet
# expects this order.
SHOP_ORDER = ["HAR", "MKT", "STN"]


def data_dir(cli_value: Optional[str] = None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser()
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_DIR)


def shop_sort_key(code: str):
    try:
        return (0, SHOP_ORDER.index(code))
    except ValueError:
        return (1, code)
