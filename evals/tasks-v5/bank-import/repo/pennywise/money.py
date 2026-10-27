"""Parsing and formatting money. Everything internal is integer cents."""

from .errors import InvalidInput

SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}
_STRIP = "£€$  "


def parse_amount(text, decimal="."):
    """Parse a human or bank-export amount into integer cents.

    Accepts thousands separators ("1,234.56", or "1.234,56" with decimal=","),
    a leading or trailing minus, parentheses for negatives ("(4.50)"), and
    currency symbols. An empty string is an error, not zero.
    """
    if text is None:
        raise InvalidInput("missing amount")
    s = str(text).strip().strip(_STRIP)
    if not s:
        raise InvalidInput("empty amount")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.endswith("-"):
        negative, s = not negative, s[:-1]
    if s.startswith("-"):
        negative, s = not negative, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    s = s.strip(_STRIP)
    thousands = "," if decimal == "." else "."
    s = s.replace(thousands, "").replace(" ", "")
    if decimal != ".":
        s = s.replace(decimal, ".")
    whole, _, frac = s.partition(".")
    if not whole:
        whole = "0"
    if not whole.isdigit() or (frac and not frac.isdigit()) or len(frac) > 2:
        raise InvalidInput(f"not an amount: {text!r}")
    cents = int(whole) * 100 + int(frac.ljust(2, "0") or 0)
    return -cents if negative else cents


def to_decimal_str(cents):
    """-450 -> '-4.50'. Used in JSON output and exports."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def format_cents(cents, currency=None):
    """-123456 -> '-£1,234.56' (symbol only when a currency is given)."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    symbol = SYMBOLS.get(currency or "", "")
    return f"{sign}{symbol}{cents // 100:,}.{cents % 100:02d}"


def split_evenly(cents, parts):
    """Split an amount into `parts` integer pieces that add back up exactly."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    base, extra = divmod(abs(cents), parts)
    pieces = [base + (1 if i < extra else 0) for i in range(parts)]
    return [-p for p in pieces] if cents < 0 else pieces


def percent(part, whole):
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)
