"""Small text helpers."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-") or "untitled"


def truncate(text: str, width: int = 40) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def snippet(body: str, query: str, radius: int = 30) -> str:
    """A bit of ``body`` around the first hit of ``query``."""
    i = body.lower().find(query.lower())
    if i < 0:
        return truncate(body, radius * 2)
    start = max(0, i - radius)
    end = min(len(body), i + len(query) + radius)
    return ("…" if start else "") + body[start:end] + ("…" if end < len(body) else "")
