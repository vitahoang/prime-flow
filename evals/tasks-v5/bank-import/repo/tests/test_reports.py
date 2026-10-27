from pennywise.budget import status, total
from pennywise.reports import monthly, months_with_data, top_spending
from tests.conftest import d


def setup(store):
    a = store.add_account("Main")
    food = store.add_category("Food")
    move = store.add_category("Card payment", kind="transfer")
    store.add_transaction(a.id, d("2025-08-01"), 300000, "Invoice")
    store.add_transaction(a.id, d("2025-08-03"), -4500, "Tesco", category_id=food.id)
    store.add_transaction(a.id, d("2025-08-04"), -41230, "Card payment", category_id=move.id)
    store.add_transaction(a.id, d("2025-09-01"), -999, "Later")
    return a, food


def test_monthly_excludes_transfers(store):
    setup(store)
    rep = monthly(store, 2025, 8)
    assert rep.income_cents == 300000
    assert rep.spending_cents == -4500
    assert rep.count == 2
    assert rep.by_category == {"Uncategorised": 300000, "Food": -4500}
    assert rep.savings_rate == 98.5


def test_top_spending_and_months(store):
    setup(store)
    assert top_spending(monthly(store, 2025, 8)) == [("Food", -4500)]
    assert months_with_data(store) == ["2025-08", "2025-09"]


def test_budget_status(store):
    _, food = setup(store)
    store.set_budget(food.id, 4000)
    lines = status(store, 2025, 8)
    assert [(l.category, l.spent_cents, l.over) for l in lines] == [("Food", 4500, True)]
    assert total(lines) == (4000, 4500)
