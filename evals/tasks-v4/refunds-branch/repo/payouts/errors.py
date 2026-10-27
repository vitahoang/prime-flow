"""Exception hierarchy.

Everything the CLI should report as a normal error (rather than a crash)
derives from PayoutsError.
"""


class PayoutsError(Exception):
    """Base class for expected, user-facing failures."""


class NotFound(PayoutsError):
    """A merchant, charge or other record does not exist."""


class ValidationError(PayoutsError):
    """Input was well-formed but not acceptable."""


class MoneyError(ValidationError):
    """An amount could not be parsed or is out of range."""


class InsufficientFunds(PayoutsError):
    """A payout asked for more than the merchant's balance."""
