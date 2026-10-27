"""Customer admin: create, update, and goodwill credit."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import subscriptions
from .models import Customer
from .money import check_currency, parse_amount
from .store import Store


class CustomerError(ValueError):
    pass


def _check_timezone(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise CustomerError(f"unknown timezone {tz!r}") from None
    return tz


def create(store: Store, customer_id: str, name: str, *, email: str, country: str, currency: str,
           timezone_name: str, plan_id: str, at: Optional[datetime] = None) -> Customer:
    if customer_id in store.customers:
        raise CustomerError(f"{customer_id} exists")
    if len(country or "") != 2:
        raise CustomerError("country must be an ISO alpha-2 code")
    customer = Customer(
        id=customer_id,
        name=name,
        email=email,
        country=country.upper(),
        currency=check_currency(currency),
        timezone=_check_timezone(timezone_name),
        plan_id=plan_id,
        created_at=(at or datetime.now(timezone.utc)),
    )
    store.customers[customer_id] = customer
    subscriptions.subscribe(store, customer_id, plan_id, at=customer.created_at)
    store.save_customers()
    return customer


def set_timezone(store: Store, customer_id: str, tz: str) -> Customer:
    customer = store.customer(customer_id)
    customer.timezone = _check_timezone(tz)
    store.save_customers()
    return customer


def grant_credit(store: Store, customer_id: str, amount) -> Customer:
    """Add goodwill credit (major units, customer's currency), e.g. after an outage."""
    value = parse_amount(amount)
    if value <= 0:
        raise CustomerError("credit must be positive")
    customer = store.customer(customer_id)
    customer.credit_balance += value
    store.save_customers()
    return customer


def remove_credit(store: Store, customer_id: str, amount) -> Customer:
    value = parse_amount(amount)
    customer = store.customer(customer_id)
    if value > customer.credit_balance:
        raise CustomerError("cannot remove more credit than the balance")
    customer.credit_balance -= value
    store.save_customers()
    return customer


def balance(store: Store, customer_id: str) -> Decimal:
    return store.customer(customer_id).credit_balance
