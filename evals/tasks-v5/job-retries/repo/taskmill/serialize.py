"""Payload parsing and error formatting."""

from __future__ import annotations

import json
import traceback
from typing import Any

MAX_ERROR_CHARS = 4000


class PayloadError(ValueError):
    pass


def parse_payload(text: str | None) -> dict[str, Any]:
    """Parse a payload given on the command line. Accepts JSON objects or
    ``key=value`` pairs separated by commas."""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PayloadError(f"payload is not valid JSON: {exc}") from None
        if not isinstance(value, dict):
            raise PayloadError("payload must be a JSON object")
        return value
    out: dict[str, Any] = {}
    for part in text.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise PayloadError(f"expected key=value, got {part!r}")
        key, _, val = part.partition("=")
        out[key.strip()] = _coerce(val.strip())
    return out


def _coerce(val: str) -> Any:
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    for cast in (int, float):
        try:
            return cast(val)
        except ValueError:
            pass
    return val


def format_error(exc: BaseException) -> str:
    """Traceback text for ``last_error``, trimmed to fit the column comfortably."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    if len(text) > MAX_ERROR_CHARS:
        text = "...\n" + text[-MAX_ERROR_CHARS:]
    return text


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, default=str)
