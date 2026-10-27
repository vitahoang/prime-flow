import pytest

from meterly import store as store_mod, subscriptions
from meterly.models import Plan, parse_ts


def test_history_sorted(store):
    plans = [s.plan_id for s in subscriptions.history(store, "cus_harbour")]
    assert plans == ["starter_gbp", "pro_gbp"]


def test_plan_at(store):
    assert subscriptions.plan_at(store, "cus_harbour", parse_ts("2026-08-18T14:04:59Z")).id == "starter_gbp"
    assert subscriptions.plan_at(store, "cus_harbour", parse_ts("2026-08-18T14:05:00Z")).id == "pro_gbp"


def test_plan_at_before_signup(store):
    with pytest.raises(subscriptions.SubscriptionError):
        subscriptions.plan_at(store, "cus_lindgren", parse_ts("2026-01-01T00:00:00Z"))


def test_changes_between(store):
    lo, hi = parse_ts("2026-08-01T00:00:00Z"), parse_ts("2026-09-01T00:00:00Z")
    assert [s.plan_id for s in subscriptions.changes_between(store, "cus_harbour", lo, hi)] == ["pro_gbp"]


def test_change_plan_updates_customer_and_history(store, data_dir):
    at = parse_ts("2026-09-20T10:00:00Z")
    store.plans["pro_eur"] = Plan.from_dict(
        {"id": "pro_eur", "currency": "EUR", "base_fee": "89.00", "tiers": [{"up_to": None, "unit_price": "0.003"}]})
    store.save_plans()
    subscriptions.change_plan(store, "cus_lindgren", "pro_eur", at)
    again = store_mod.load(data_dir)
    assert again.customer("cus_lindgren").plan_id == "pro_eur"
    assert [s.plan_id for s in subscriptions.history(again, "cus_lindgren")] == ["starter_eur", "pro_eur"]


def test_change_plan_rejects_other_currency(store):
    with pytest.raises(subscriptions.SubscriptionError):
        subscriptions.change_plan(store, "cus_harbour", "scale_usd")


def test_change_to_same_plan(store):
    with pytest.raises(subscriptions.SubscriptionError):
        subscriptions.change_plan(store, "cus_harbour", "pro_gbp")
