"""Money helpers.

Convention: every amount in this codebase is an ``int`` number of minor units
of the merchant's currency: cents for USD/EUR/GBP, whole yen for JPY (which
has no minor unit). Fields are still called ``*_cents`` from before we took
JPY merchants; read them as "minor units".

Amounts only become strings at the edges: ``parse_amount(text, currency)``
turns user input ("19.99", or "500" for yen) into minor units, and
``format_cents(amount, currency)`` turns them back for display. Rates go
through Decimal (see ``apply_bps``).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

from payouts.errors import MoneyError

DEFAULT_CURRENCY = "USD"

# Decimal places of each currency we settle in (ISO 4217 exponent).
EXPONENTS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}

MAX_AMOUNT_MAJOR = Decimal(10_000_000)  # 10M major units, well above any single charge


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency.upper()]
    except (KeyError, AttributeError):
        raise MoneyError(f"unsupported currency: {currency!r}") from None


def parse_amount(text: str | int, currency: str = DEFAULT_CURRENCY, *, allow_zero: bool = False) -> int:
    """Parse a user-supplied amount in major units into integer minor units.

    parse_amount("19.99") == 1999, parse_amount("500", "JPY") == 500.
    Accepts "19.99", "19.9", "19", "$19.99" and "1,019.99". Rejects negative
    amounts, more decimal places than the currency has, and anything that
    isn't a number.
    """
    exp = exponent(currency)
    if isinstance(text, bool):
        raise MoneyError(f"not an amount: {text!r}")
    if isinstance(text, int):
        text = str(text)
    if not isinstance(text, str):
        raise MoneyError(f"amounts must be given as strings, got {type(text).__name__}")
    cleaned = text.strip().replace(",", "")
    if cleaned[:1] in ("$", "€", "£", "¥"):
        cleaned = cleaned[1:]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise MoneyError(f"not an amount: {text!r}") from None
    if not value.is_finite():
        raise MoneyError(f"not an amount: {text!r}")
    if abs(value) > MAX_AMOUNT_MAJOR:
        raise MoneyError(f"amount too large: {text!r}")
    quantum = Decimal(1).scaleb(-exp)
    if value != value.quantize(quantum):
        places = "no decimal places" if exp == 0 else f"at most {exp} decimal places"
        raise MoneyError(f"{currency.upper()} amounts have {places}: {text!r}")
    minor = int(value.scaleb(exp))
    if minor < 0:
        raise MoneyError(f"amount must not be negative: {text!r}")
    if minor == 0 and not allow_zero:
        raise MoneyError("amount must be greater than zero")
    return minor


def format_cents(amount: int, currency: str = DEFAULT_CURRENCY, *, signed: bool = False) -> str:
    """1999 -> '19.99', -50 -> '-0.50', (500, 'JPY') -> '500'; signed=True adds '+'."""
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise TypeError(f"format_cents wants int minor units, got {type(amount).__name__}")
    exp = exponent(currency)
    sign = "-" if amount < 0 else ("+" if signed and amount > 0 else "")
    if exp == 0:
        return f"{sign}{abs(amount)}"
    whole, frac = divmod(abs(amount), 10**exp)
    return f"{sign}{whole}.{frac:0{exp}d}"


def apply_bps(amount: int, bps: int) -> int:
    """Return ``amount * bps / 10000`` rounded half-up to a whole minor unit."""
    value = Decimal(amount) * Decimal(bps) / Decimal(10_000)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def sum_cents(amounts: Iterable[int]) -> int:
    total = 0
    for amount in amounts:
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"sum_cents wants int minor units, got {type(amount).__name__}")
        total += amount
    return total
