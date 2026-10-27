import pytest

from pennywise.errors import InvalidInput, NotFound
from tests.conftest import d


def test_add_and_get_account(store):
    a = store.add_account("Northbank", bank="northbank")
    assert store.get_account("northbank").id == a.id
    with pytest.raises(InvalidInput):
        store.add_account("NORTHBANK")
    with pytest.raises(NotFound):
        store.get_account("nope")


def test_transactions_and_balance(store):
    a = store.add_account("Main")
    store.add_transaction(a.id, d("2025-08-01"), 100000, "Salary")
    store.add_transaction(a.id, d("2025-08-02"), -450, "Coffee")
    assert store.balance(a.id) == 99550
    assert store.count_transactions(a.id) == 2
    assert store.last_transaction_date(a.id) == d("2025-08-02")


def test_list_filters(store):
    a = store.add_account("Main")
    food = store.add_category("Food")
    store.add_transaction(a.id, d("2025-07-31"), -100, "old")
    t = store.add_transaction(a.id, d("2025-08-01"), -200, "new", category_id=food.id)
    store.add_transaction(a.id, d("2025-08-02"), -300, "uncat")
    aug = store.list_transactions(account_id=a.id, start=d("2025-08-01"), end=d("2025-08-31"))
    assert [x.description for x in aug] == ["new", "uncat"]
    assert [x.id for x in store.list_transactions(category_id=food.id)] == [t]
    assert [x.description for x in store.list_transactions(uncategorized=True)] == ["old", "uncat"]
    assert len(store.list_transactions(limit=1)) == 1


def test_categories_unique_case_insensitive(store):
    store.add_category("Groceries")
    with pytest.raises(InvalidInput):
        store.add_category("groceries")
    assert store.ensure_category("GROCERIES").name == "Groceries"


def test_set_category_and_delete(store):
    a = store.add_account("Main")
    cat = store.add_category("Fun")
    t = store.add_transaction(a.id, d("2025-08-01"), -100, "x")
    store.set_category(t, cat.id)
    assert store.get_transaction(t).category_id == cat.id
    store.delete_transaction(t)
    with pytest.raises(NotFound):
        store.get_transaction(t)


def test_close_account_hides_it(store):
    store.add_account("Old")
    store.add_account("New")
    store.close_account("Old", on=d("2025-01-01"))
    assert [a.name for a in store.list_accounts()] == ["New"]
    assert len(store.list_accounts(include_closed=True)) == 2


def test_budget_upsert(store):
    cat = store.add_category("Food")
    store.set_budget(cat.id, 10000)
    store.set_budget(cat.id, 20000)
    assert [(b.category_id, b.amount_cents) for b in store.list_budgets()] == [(cat.id, 20000)]
