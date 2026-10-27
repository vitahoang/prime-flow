"""User settings.

Settings live in ``config.json`` inside the ledger home directory
(``$LEDGER_HOME``, default ``~/.ledger``). Any key missing from the file
falls back to ``DEFAULTS``.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULTS = {
    # IANA timezone the user lives in. Entries are stored in UTC and
    # converted to this zone whenever they are shown.
    "timezone": "America/Chicago",
    # strftime format used when showing a date to the user.
    "date_format": "%m/%d/%Y",
    # Currency symbol used by the display formatter.
    "currency_symbol": "$",
}


def ledger_home() -> Path:
    return Path(os.environ.get("LEDGER_HOME", Path.home() / ".ledger"))


@dataclass(frozen=True)
class Settings:
    timezone: str
    date_format: str
    currency_symbol: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    values = dict(DEFAULTS)
    path = ledger_home() / "config.json"
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            values.update(json.load(fh))
    return Settings(
        timezone=values["timezone"],
        date_format=values["date_format"],
        currency_symbol=values["currency_symbol"],
    )
