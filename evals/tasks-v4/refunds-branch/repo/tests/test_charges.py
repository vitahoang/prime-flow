import pytest

from payouts import ledger
from payouts.charges import charges_for, create_charge, get_charge
from payouts.errors import NotFound, ValidationError
from payouts.gateway import FakeGateway, GatewayDeclined, GatewayTimeout
from payouts.merchants import create_merchant, suspend_merchant


@pytest.fixture
def merchant(store):
    return create_merchant(store, "Acme")


def test_charge_credits_merchant_less_fee(store, merchant):
    charge = create_charge(store, FakeGateway(store, faults=[]), merchant.id, 10000, "order 1")
    assert charge.fee_cents == 290 + 30
    assert ledger.balance(store, merchant.id) == 10000 - 320
    assert get_charge(store, charge.id) == charge
    assert charges_for(store, merchant.id) == [charge]


def test_zero_fee_merchant(store):
    m = create_merchant(store, "Free", fee_bps=0, fee_fixed_cents=0)
    create_charge(store, FakeGateway(store, faults=[]), m.id, 1999)
    assert ledger.balance(store, m.id) == 1999
    assert [e.kind for e in ledger.entries_for(store, m.id)] == ["charge"]


def test_jpy_charge(store):
    m = create_merchant(store, "Tokyo Tea", currency="JPY", fee_bps=290, fee_fixed_cents=0)
    charge = create_charge(store, FakeGateway(store, faults=[]), m.id, 5000)
    assert charge.currency == "JPY"
    assert charge.fee_cents == 145
    assert ledger.balance(store, m.id) == 4855


def test_fee_capped_at_amount(store, merchant):
    charge = create_charge(store, FakeGateway(store, faults=[]), merchant.id, 20)
    assert charge.fee_cents == 20
    assert ledger.balance(store, merchant.id) == 0


def test_rejects_non_positive(store, merchant):
    with pytest.raises(ValidationError):
        create_charge(store, FakeGateway(store, faults=[]), merchant.id, 0)


def test_suspended_merchant(store, merchant):
    suspend_merchant(store, merchant.id)
    with pytest.raises(ValidationError):
        create_charge(store, FakeGateway(store, faults=[]), merchant.id, 100)


def test_unknown_merchant(store):
    with pytest.raises(NotFound):
        create_charge(store, FakeGateway(store, faults=[]), "m_0404", 100)


def test_timeout_is_retried(store, merchant):
    gw = FakeGateway(store, faults=[("charge", "timeout")])
    create_charge(store, gw, merchant.id, 1000)
    assert len(gw.operations()) == 1


def test_gives_up_after_three_timeouts(store, merchant):
    gw = FakeGateway(store, faults=[("charge", "timeout")] * 3)
    with pytest.raises(GatewayTimeout):
        create_charge(store, gw, merchant.id, 1000)
    assert ledger.balance(store, merchant.id) == 0


def test_decline_records_nothing(store, merchant):
    gw = FakeGateway(store, faults=[("charge", "decline")])
    with pytest.raises(GatewayDeclined):
        create_charge(store, gw, merchant.id, 1000)
    assert charges_for(store, merchant.id) == []


def test_lost_response_not_charged_twice(store, merchant):
    # INC-212: the processor took the money, we timed out, retried, and the
    # customer was charged twice.
    gw = FakeGateway(store, faults=[("charge", "lost")])
    create_charge(store, gw, merchant.id, 1000)
    assert len([op for op in gw.operations() if op["op"] == "charge"]) == 1
    assert len(charges_for(store, merchant.id)) == 1
