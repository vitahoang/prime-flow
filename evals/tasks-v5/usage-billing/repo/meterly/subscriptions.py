"""Plan history.

subscriptions.json keeps one record per plan a customer has been on, with the
moment it started. Customer.plan_id is the current plan; change_plan keeps the
two in step.
"""

from datetime import datetime, timezone
from typing import List, Optional

from .models import Plan, Subscription
from .store import Store


class SubscriptionError(ValueError):
    pass


def history(store: Store, customer_id: str) -> List[Subscription]:
    """The customer's plan records, oldest first."""
    return sorted((s for s in store.subscriptions if s.customer_id == customer_id),
                  key=lambda s: s.started_at)


def subscription_at(store: Store, customer_id: str, when: datetime) -> Optional[Subscription]:
    current = None
    for sub in history(store, customer_id):
        if sub.started_at <= when:
            current = sub
        else:
            break
    return current


def plan_at(store: Store, customer_id: str, when: datetime) -> Plan:
    """The plan the customer was on at instant ``when``."""
    sub = subscription_at(store, customer_id, when)
    if sub is None:
        raise SubscriptionError(f"{customer_id} had no plan at {when.isoformat()}")
    return store.plan(sub.plan_id)


def changes_between(store: Store, customer_id: str, start: datetime, end: datetime) -> List[Subscription]:
    """Plan records that started inside [start, end)."""
    return [s for s in history(store, customer_id) if start <= s.started_at < end]


def subscribe(store: Store, customer_id: str, plan_id: str, at: Optional[datetime] = None) -> Subscription:
    """First plan for a new customer."""
    if history(store, customer_id):
        raise SubscriptionError(f"{customer_id} already has a plan; use change_plan")
    return _start(store, customer_id, plan_id, at)


def change_plan(store: Store, customer_id: str, plan_id: str, at: Optional[datetime] = None) -> Subscription:
    """Move a customer to another plan from ``at`` (default now)."""
    customer = store.customer(customer_id)
    if customer.plan_id == plan_id:
        raise SubscriptionError(f"{customer_id} is already on {plan_id}")
    return _start(store, customer_id, plan_id, at)


def _start(store: Store, customer_id: str, plan_id: str, at: Optional[datetime]) -> Subscription:
    plan = store.plan(plan_id)
    customer = store.customer(customer_id)
    if plan.currency != customer.currency:
        raise SubscriptionError(f"plan {plan_id} is priced in {plan.currency}, customer pays in {customer.currency}")
    at = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sub = Subscription(customer_id=customer_id, plan_id=plan_id, started_at=at)
    store.subscriptions.append(sub)
    customer.plan_id = plan_id
    store.save_subscriptions()
    store.save_customers()
    return sub
