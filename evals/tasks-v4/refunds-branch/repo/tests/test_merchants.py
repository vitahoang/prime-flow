import pytest

from payouts.errors import NotFound, ValidationError
from payouts.merchants import create_merchant, get_merchant, list_merchants, reactivate_merchant, suspend_merchant


def test_create_with_defaults(store):
    m = create_merchant(store, "Acme Ltd")
    assert m.id == "m_0001"
    assert (m.fee_bps, m.fee_fixed_cents) == (290, 30)
    assert get_merchant(store, m.id) == m


def test_currency(store):
    m = create_merchant(store, "Tokyo Tea", currency="jpy")
    assert m.currency == "JPY"
    with pytest.raises(ValidationError):
        create_merchant(store, "Mars", currency="XYZ")


def test_name_required(store):
    with pytest.raises(ValidationError):
        create_merchant(store, "  ")


def test_duplicate_name(store):
    create_merchant(store, "Acme")
    with pytest.raises(ValidationError):
        create_merchant(store, "acme")


def test_fee_bounds(store):
    with pytest.raises(ValidationError):
        create_merchant(store, "Greedy", fee_bps=5000)
    with pytest.raises(ValidationError):
        create_merchant(store, "Odd", fee_fixed_cents=-1)


def test_missing(store):
    with pytest.raises(NotFound):
        get_merchant(store, "m_9999")


def test_suspend_and_list(store):
    a = create_merchant(store, "A")
    b = create_merchant(store, "B")
    suspend_merchant(store, a.id)
    assert [m.id for m in list_merchants(store)] == [a.id, b.id]
    assert [m.id for m in list_merchants(store, include_suspended=False)] == [b.id]
    reactivate_merchant(store, a.id)
    assert get_merchant(store, a.id).active
