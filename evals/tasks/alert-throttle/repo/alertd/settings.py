"""Per-user settings: who gets alerted, and where."""

import json
from dataclasses import dataclass, asdict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidSettings(ValueError):
    pass


@dataclass
class UserSettings:
    """Settings for the person on call.

    ``timezone`` is an IANA name (e.g. "Europe/Berlin"). Message timestamps are
    rendered in this zone; see ``alertd.formatting``.
    """

    user_id: str
    timezone: str = "UTC"
    email: str = ""
    phone: str = ""
    slack_handle: str = ""

    def __post_init__(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidSettings(f"unknown timezone: {self.timezone!r}")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def to_dict(self) -> dict:
        return asdict(self)


def settings_from_dict(data: dict) -> UserSettings:
    if "user_id" not in data:
        raise InvalidSettings("settings need a user_id")
    known = {"user_id", "timezone", "email", "phone", "slack_handle"}
    unknown = set(data) - known
    if unknown:
        raise InvalidSettings(f"unknown settings keys: {sorted(unknown)}")
    return UserSettings(**data)


def load_settings(path: str) -> UserSettings:
    with open(path, encoding="utf-8") as fh:
        return settings_from_dict(json.load(fh))


def save_settings(settings: UserSettings, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(settings.to_dict(), fh, indent=2)
