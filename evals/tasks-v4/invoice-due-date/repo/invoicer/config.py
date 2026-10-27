"""Runtime configuration.

Most settings are constants for now; the two things that change between
machines (where the data lives and, for testing, what time it is) come from
environment variables.
"""

import os
from decimal import Decimal
from pathlib import Path

DATA_DIR_ENV = "INVOICER_DATA_DIR"
NOW_ENV = "INVOICER_NOW"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BUSINESS_NAME = "Hollis & Rye Studio"
BUSINESS_ADDRESS = ("14 Cable Street", "London E1 8JG", "United Kingdom")
BUSINESS_EMAIL = "accounts@hollisrye.example"
BUSINESS_TZ = "Europe/London"

# Late fee: a percentage of the outstanding balance, with a floor, charged
# once an invoice is overdue.
LATE_FEE_RATE = Decimal("0.02")
LATE_FEE_MINIMUM = Decimal("10.00")

# Payment reminders go out this many days before the due date.
REMINDER_DAYS_BEFORE = (7, 1)

DEFAULT_TERMS_DAYS = 30
DEFAULT_CURRENCY = "GBP"


def data_dir() -> Path:
    """The directory holding customers.json, invoices.json and payments.json."""
    raw = os.environ.get(DATA_DIR_ENV)
    return Path(raw).expanduser() if raw else DEFAULT_DATA_DIR
