"""Money helpers. Amounts are Decimals rounded to the currency's minor unit."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Currencies we bill in, with their minor-unit digits.
CURRENCIES = {
    "GBP": 2,
    "USD": 2,
    "AUD": 2,
    "SGD": 2,
    "EUR": 2,
    "NOK": 2,
    "INR": 2,
    "JPY": 0,
}

SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}

CENT = Decimal("0.01")


def round_money(amount: Decimal, currency: str = "GBP") -> Decimal:
    digits = CURRENCIES.get(currency, 2)
    quantum = Decimal(1).scaleb(-digits)
    return Decimal(amount).quantize(quantum, rounding=ROUND_HALF_UP)


def parse_amount(raw) -> Decimal:
    """Parse an amount from the data file (string or number)."""
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"not an amount: {raw!r}") from exc


def format_money(amount: Decimal, currency: str) -> str:
    """'SGD 1,200.00'. Currencies with a well-known symbol still use the code,
    because half our customers would otherwise read '$' as their own dollar."""
    digits = CURRENCIES.get(currency, 2)
    value = round_money(amount, currency)
    sign = "-" if value < 0 else ""
    body = f"{abs(value):,.{digits}f}"
    return f"{currency} {sign}{body}"


def format_money_html(amount: Decimal, currency: str) -> str:
    return format_money(amount, currency).replace(" ", "&nbsp;", 1)


def sum_money(amounts, currency: str = "GBP") -> Decimal:
    return round_money(sum(amounts, Decimal("0")), currency)


def percent(amount: Decimal, rate: Decimal, currency: str = "GBP") -> Decimal:
    return round_money(amount * rate, currency)


def round_half_even_old(amount):
    """Old rounding used before 0.5. Kept until the 2024 books are closed."""
    return Decimal(amount).quantize(CENT)
