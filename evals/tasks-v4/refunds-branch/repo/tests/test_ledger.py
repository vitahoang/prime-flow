import pytest

from payouts import ledger
from payouts.errors import ValidationError


def test_balance_is_sum(store):
    ledger.record(store, "m_0001", ledger.CHARGE, 1000, ref="ch_0001")
    ledger.record(store, "m_0001", ledger.FEE, -59, ref="ch_0001")
    ledger.record(store, "m_0002", ledger.CHARGE, 500, ref="ch_0002")
    assert ledger.balance(store, "m_0001") == 941
    assert ledger.balance(store, "m_0002") == 500


def test_sign_rules(store):
    with pytest.raises(ValidationError):
        ledger.record(store, "m_0001", ledger.CHARGE, -1, ref="x")
    with pytest.raises(ValidationError):
        ledger.record(store, "m_0001", ledger.PAYOUT, 1, ref="x")
    ledger.record(store, "m_0001", ledger.ADJUSTMENT, -1, ref="x")
    ledger.record(store, "m_0001", ledger.ADJUSTMENT, 1, ref="x")


def test_unknown_kind(store):
    with pytest.raises(ValidationError):
        ledger.record(store, "m_0001", "bonus", 1, ref="x")


def test_int_cents_only(store):
    with pytest.raises(ValidationError):
        ledger.record(store, "m_0001", ledger.CHARGE, 10.5, ref="x")


def test_zero_rejected(store):
    with pytest.raises(ValidationError):
        ledger.record(store, "m_0001", ledger.CHARGE, 0, ref="x")


def test_totals_by_kind(store):
    ledger.record(store, "m_0001", ledger.CHARGE, 1000, ref="a")
    ledger.record(store, "m_0001", ledger.CHARGE, 500, ref="b")
    ledger.record(store, "m_0001", ledger.FEE, -40, ref="a")
    assert ledger.totals_by_kind(store, "m_0001") == {"charge": 1500, "fee": -40}
