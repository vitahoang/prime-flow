"""How each bank lays out its CSV export.

An account's ``bank`` field names one of these profiles (``manual`` accounts
have none). Real exports for each bank are in samples/.
"""

from dataclasses import dataclass
from typing import Optional

from .errors import NotFound


@dataclass(frozen=True)
class BankProfile:
    key: str
    label: str
    delimiter: str = ","
    decimal: str = "."
    encoding: str = "utf-8-sig"
    date_column: str = "Date"
    date_format: Optional[str] = None  # strptime format; None falls back to dates.DEFAULT_FORMAT
    description_column: str = "Description"
    # Either one signed amount column, or separate paid-in / paid-out columns
    # that are both written as positive numbers.
    amount_column: Optional[str] = "Amount"
    paid_in_column: Optional[str] = None
    paid_out_column: Optional[str] = None
    # The bank's own id for each transaction, when the export has one.
    reference_column: Optional[str] = None
    # Card exports show purchases as positive; flip them so money out is
    # negative like everywhere else (refunds and payments then come out positive).
    invert_amounts: bool = False
    # Rows whose type column holds one of these are skipped: Northbank lists
    # pending card payments as PND, and they come back days later as DEB rows.
    type_column: Optional[str] = None
    skip_types: tuple = ()
    currency: str = "GBP"

    @property
    def required_columns(self):
        cols = [self.date_column, self.description_column]
        if self.amount_column:
            cols.append(self.amount_column)
        else:
            cols += [self.paid_in_column, self.paid_out_column]
        if self.reference_column:
            cols.append(self.reference_column)
        return cols

    def missing_columns(self, header):
        present = {h.strip() for h in header}
        return [c for c in self.required_columns if c not in present]


PROFILES = {
    "northbank": BankProfile(
        key="northbank",
        label="Northbank current account",
        date_format="%d/%m/%Y",
        amount_column=None,
        paid_in_column="Paid in",
        paid_out_column="Paid out",
        type_column="Type",
        skip_types=("PND",),
    ),
    "kestrel": BankProfile(
        key="kestrel",
        label="Kestrel euro account",
        delimiter=";",
        decimal=",",
        date_format="%d.%m.%Y",
        reference_column="ID",
        currency="EUR",
    ),
    # US card: month-first dates (see samples/uscard-2025-08.csv).
    "uscard": BankProfile(
        key="uscard",
        label="Liberty Rewards Visa",
        date_column="Transaction Date",
        date_format="%d/%m/%Y",
        invert_amounts=True,
        currency="USD",
    ),
}

BANKS = ("manual",) + tuple(PROFILES)


def get_profile(key):
    try:
        return PROFILES[key]
    except KeyError:
        raise NotFound(f"no CSV profile for bank {key!r}") from None
