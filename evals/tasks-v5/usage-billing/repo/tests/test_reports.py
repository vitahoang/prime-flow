from datetime import date

from meterly import reports


def test_activity_counts_calls(store):
    rows = {r["customer"]: r for r in reports.activity(store, date(2026, 9, 1), date(2026, 10, 1))}
    assert rows["cus_lindgren"]["calls"] == 1
    assert rows["cus_sakura"]["calls"] == 1
    assert rows["cus_harbour"]["tags"] == ["priority-support"]


def test_inactive(store):
    assert set(reports.inactive(store, date(2026, 7, 1), date(2026, 8, 1))) == set(store.customers)
    assert "cus_harbour" not in reports.inactive(store, date(2026, 9, 1), date(2026, 10, 1))


def test_plan_mix(store):
    assert reports.plan_mix(store) == {"pro_gbp": 1, "pro_jpy": 1, "scale_usd": 1, "starter_eur": 1}
