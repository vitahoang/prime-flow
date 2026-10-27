"""JSON file store.

A data directory holds:

    customers.json      list of customers
    plans.json          list of plans
    subscriptions.json  plan history: one record per (customer, plan, started_at)
    events.jsonl        usage events, one JSON object per line, append-only

The store loads everything into memory; our biggest customer sends a few
hundred thousand events a month, which is fine.
"""

import json
from pathlib import Path
from typing import Dict, List

from . import config
from .models import Customer, Plan, Subscription, UsageEvent

CUSTOMERS = "customers.json"
PLANS = "plans.json"
SUBSCRIPTIONS = "subscriptions.json"
EVENTS = "events.jsonl"


class StoreError(Exception):
    pass


class UnknownCustomer(StoreError, KeyError):
    pass


class UnknownPlan(StoreError, KeyError):
    pass


def _read_json(path: Path, default):
    if not path.exists():
        return default
    text = path.read_text()
    if not text.strip():
        return default
    return json.loads(text)


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.customers: Dict[str, Customer] = {}
        self.plans: Dict[str, Plan] = {}
        self.subscriptions: List[Subscription] = []
        self.events: List[UsageEvent] = []

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, root=None) -> "Store":
        store = cls(config.data_dir(root))
        for d in _read_json(store.root / CUSTOMERS, []):
            c = Customer.from_dict(d)
            store.customers[c.id] = c
        for d in _read_json(store.root / PLANS, []):
            p = Plan.from_dict(d)
            store.plans[p.id] = p
        store.subscriptions = [Subscription.from_dict(d) for d in _read_json(store.root / SUBSCRIPTIONS, [])]
        events_path = store.root / EVENTS
        if events_path.exists():
            with events_path.open() as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        store.events.append(UsageEvent.from_dict(json.loads(line)))
                    except (ValueError, KeyError) as exc:
                        raise StoreError(f"{events_path}:{lineno}: bad event: {exc}") from None
        return store

    # -- lookups -----------------------------------------------------------

    def customer(self, customer_id: str) -> Customer:
        try:
            return self.customers[customer_id]
        except KeyError:
            raise UnknownCustomer(customer_id) from None

    def plan(self, plan_id: str) -> Plan:
        try:
            return self.plans[plan_id]
        except KeyError:
            raise UnknownPlan(plan_id) from None

    def events_of(self, customer_id: str) -> List[UsageEvent]:
        return [e for e in self.events if e.customer_id == customer_id]

    # -- writing -----------------------------------------------------------

    def save_customers(self):
        self._write(CUSTOMERS, [c.to_dict() for c in self.customers.values()])

    def save_plans(self):
        self._write(PLANS, [p.to_dict() for p in self.plans.values()])

    def save_subscriptions(self):
        self._write(SUBSCRIPTIONS, [s.to_dict() for s in self.subscriptions])

    def append_event(self, event: UsageEvent):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / EVENTS).open("a") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")
        self.events.append(event)

    def _write(self, name, payload):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / (name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(self.root / name)


def load(root=None) -> Store:
    return Store.load(root)
