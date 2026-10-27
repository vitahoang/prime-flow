"""Small shared helpers (added for refunds)."""

from __future__ import annotations


def _to_amount(value) -> int:
    """Normalise an amount from the CLI or a caller into cents.

    Accepts what people actually type ("12.50", "$12.50", "12") as well as
    an already-converted int.
    """
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "").lstrip("$")
    return int(float(text) * 100)


def _display(cents: int) -> str:
    return f"{cents / 100:.2f}"


def truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."
