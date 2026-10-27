"""Runtime configuration.

The data directory comes from ``$METERLY_DATA`` (or an explicit override, which
the CLI passes from ``--data``). Everything else here is a plain constant.
"""

import os
from decimal import Decimal
from pathlib import Path

DATA_ENV = "METERLY_DATA"
DEFAULT_DATA_DIR = Path.home() / ".meterly"

# VAT added to every invoice. We bill from the UK, so it's UK VAT.
VAT_RATE = Decimal("0.20")

DEFAULT_CURRENCY = "USD"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_METRIC = "api_calls"

# Events whose timestamp is further than this in the future are rejected at
# ingest; clocks on customer machines drift, but not by a day.
MAX_CLOCK_SKEW_SECONDS = 15 * 60


def data_dir(override=None) -> Path:
    """Where the JSON files live: the override, else $METERLY_DATA, else ~/.meterly."""
    if override:
        return Path(override)
    env = os.environ.get(DATA_ENV)
    if env:
        return Path(env)
    return DEFAULT_DATA_DIR
