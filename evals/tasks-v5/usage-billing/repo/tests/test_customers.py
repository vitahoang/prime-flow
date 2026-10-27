from decimal import Decimal

import pytest

from meterly import customers, store as store_mod, subscriptions
from meterly.models import parse_ts


def test_create_subscribes(store, data_dir):
    customers.create(store, "cus_new", "New Co", email="a@b.example", country="gb", currency="GBP",
                     timezone_name="Europe/London", plan_id="starter_gbp", at=parse_ts("2026-09-10T09:00:00Z"))
    again = store_mod.load(data_dir)
    assert again.customer("cus_new").country == "GB"
    assert [s.plan_id for s in subscriptions.history(again, "cus_new")] == ["starter_gbp"]


def test_create_rejects_bad_timezone(store):
    with pytest.raises(customers.CustomerError):
        customers.create(store, "cus_bad", "Bad", email="", country="GB", currency="GBP",
                         timezone_name="Mars/Olympus", plan_id="starter_gbp")


def test_grant_and_remove_credit(store):
    customers.grant_credit(store, "cus_pinecrest", "40.00")
    assert customers.balance(store, "cus_pinecrest") == Decimal("40.00")
    customers.remove_credit(store, "cus_pinecrest", "15")
    assert customers.balance(store, "cus_pinecrest") == Decimal("25.00")
    with pytest.raises(customers.CustomerError):
        customers.remove_credit(store, "cus_pinecrest", "100")


def test_set_timezone(store):
    customers.set_timezone(store, "cus_harbour", "Europe/Dublin")
    assert store.customer("cus_harbour").timezone == "Europe/Dublin"
