"""Money helpers.

Prices in plans.json are written in major units as strings ("49.00", "0.0125")
and parsed to Decimal. Nothing in meterly should touch floats for money.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Digits after the decimal point in each currency's smallest unit.
MINOR_UNITS = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "AUD": 2,
    "CAD": 2,
    "JPY": 0,
}

SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AUD": "A$",
    "CAD": "C$",
    "JPY": "¥",
}

ZERO = Decimal("0")


class MoneyError(ValueError):
    pass


def check_currency(currency: str) -> str:
    code = (currency or "").upper()
    if code not in MINOR_UNITS:
        raise MoneyError(f"unsupported currency: {currency!r}")
    return code


def exponent(currency: str) -> int:
    """Number of decimal places in the currency's minor unit."""
    return MINOR_UNITS[check_currency(currency)]


def parse_amount(value) -> Decimal:
    """Parse a price or balance from JSON. Accepts str, int or Decimal; not float."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or isinstance(value, float):
        raise MoneyError(f"amounts must be strings or ints, got {value!r}")
    if value is None or value == "":
        return ZERO
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise MoneyError(f"not an amount: {value!r}") from None


def round_half_up(amount: Decimal, places: int = 2) -> Decimal:
    q = Decimal(1).scaleb(-places)
    return amount.quantize(q, rounding=ROUND_HALF_UP)


def to_cents(amount: Decimal) -> int:
    """Convert a major-unit amount to cents, rounding half up."""
    return int(round_half_up(amount * 100, 0))


def from_cents(cents: int) -> Decimal:
    return Decimal(cents) / 100


def format_amount(minor: int, currency: str) -> str:
    """Render an amount in minor units for humans: 4950 USD -> '$49.50', 3000 JPY -> '¥3,000'."""
    code = check_currency(currency)
    places = MINOR_UNITS[code]
    major = Decimal(minor).scaleb(-places)
    sign = "-" if major < 0 else ""
    text = f"{abs(major):,.{places}f}"
    return f"{sign}{SYMBOLS.get(code, code + ' ')}{text}"


def format_major(amount: Decimal, currency: str) -> str:
    """Render a major-unit Decimal (as stored in plans.json)."""
    code = check_currency(currency)
    places = MINOR_UNITS[code]
    minor = int(round_half_up(amount.scaleb(places), 0))
    return format_amount(minor, code)
