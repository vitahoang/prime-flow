"""Sales tax / VAT by customer country.

Kept up to date by Dana in finance. Rates are fractions of the pre-tax amount.
A country that isn't listed is one we aren't registered in: no tax.
"""

from decimal import Decimal

TAX_RATES = {
    "GB": Decimal("0.20"),
    "IE": Decimal("0.23"),
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
    "NL": Decimal("0.21"),
    "ES": Decimal("0.21"),
    "AU": Decimal("0.10"),
    "JP": Decimal("0.10"),
    "NZ": Decimal("0.15"),
}

TAX_NAMES = {
    "AU": "GST",
    "NZ": "GST",
    "JP": "Consumption tax",
}


def rate_for(country: str) -> Decimal:
    """Tax rate for a customer in ``country`` (ISO 3166 alpha-2). 0 if we don't collect there."""
    return TAX_RATES.get((country or "").upper(), Decimal("0"))


def tax_name(country: str) -> str:
    return TAX_NAMES.get((country or "").upper(), "VAT")


def describe(country: str) -> str:
    rate = rate_for(country)
    if not rate:
        return "no tax"
    pct = (rate * 100).normalize()
    return f"{tax_name(country)} {pct:f}%"
