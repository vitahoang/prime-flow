import pytest

from payouts.charges import create_charge
from payouts.gateway import FakeGateway
from payouts.merchants import create_merchant
from payouts.refunds import RefundError, create_refund, refunds_for_charge
from payouts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


@pytest.fixture
def charge(store):
    m = create_merchant(store, "Bean There", fee_bps=0, fee_fixed_cents=0)
    return create_charge(store, FakeGateway(store, faults=[]), m.id, 5000, "order 77")


def test_full_refund(store, charge):
    refund = create_refund(store, FakeGateway(store, faults=[]), charge.id, "50.00")
    assert refund.amount_cents == 5000
    assert refund.merchant_id == charge.merchant_id
    assert refunds_for_charge(store, charge.id) == [refund]


def test_partial_refund(store, charge):
    refund = create_refund(store, FakeGateway(store, faults=[]), charge.id, "12.50", reason="damaged")
    assert refund.amount_cents == 1250
    assert refund.reason == "damaged"


def test_two_partial_refunds(store, charge):
    gw = FakeGateway(store, faults=[])
    create_refund(store, gw, charge.id, "10.00")
    create_refund(store, gw, charge.id, "15.00")
    assert sum(r.amount_cents for r in refunds_for_charge(store, charge.id)) == 2500
    with pytest.raises(RefundError):
        create_refund(store, gw, charge.id, "25.01")


def test_refund_more_than_charge_rejected(store, charge):
    with pytest.raises(RefundError):
        create_refund(store, FakeGateway(store, faults=[]), charge.id, "50.50")


def test_zero_refund_rejected(store, charge):
    with pytest.raises(RefundError):
        create_refund(store, FakeGateway(store, faults=[]), charge.id, "0")


def test_refund_goes_through_gateway(store, charge):
    gw = FakeGateway(store, faults=[])
    refund = create_refund(store, gw, charge.id, "5.00")
    ops = [op for op in gw.operations() if op["op"] == "refund"]
    assert len(ops) == 1
    assert ops[0]["ref"] == refund.gateway_ref
    assert ops[0]["charge_ref"] == charge.gateway_ref
    assert ops[0]["amount_cents"] == 500


def test_refund_retries_on_timeout(store, charge):
    gw = FakeGateway(store, faults=[("refund", "timeout")])
    refund = create_refund(store, gw, charge.id, "5.00")
    assert refund.gateway_ref.startswith("gw_re_")


def test_amount_as_int_cents(store, charge):
    refund = create_refund(store, FakeGateway(store, faults=[]), charge.id, 725)
    assert refund.amount_cents == 725
    assert refund.currency == "USD"


def test_unknown_charge(store):
    from payouts.errors import NotFound

    with pytest.raises(NotFound):
        create_refund(store, FakeGateway(store, faults=[]), "ch_9999", "1.00")


def test_cumulative_refunds_cannot_exceed_charge(store, charge):
    gw = FakeGateway(store, faults=[])
    create_refund(store, gw, charge.id, "30.00")
    with pytest.raises(RefundError):
        create_refund(store, gw, charge.id, "30.00")
    create_refund(store, gw, charge.id, "20.00")
    with pytest.raises(RefundError, match="fully refunded"):
        create_refund(store, gw, charge.id, "0.01")


def test_interleaved_charges(store, charge):
    gw = FakeGateway(store, faults=[])
    other = create_charge(store, gw, charge.merchant_id, 5000, "order 78")
    create_refund(store, gw, charge.id, "25.00")
    create_refund(store, gw, other.id, "5.00")
    create_refund(store, gw, charge.id, "25.00")
    with pytest.raises(RefundError):
        create_refund(store, gw, charge.id, "0.01")


def test_exact_cents(store):
    m = create_merchant(store, "Cents", fee_bps=0, fee_fixed_cents=0)
    gw = FakeGateway(store, faults=[])
    c = create_charge(store, gw, m.id, 30, "tiny")
    create_refund(store, gw, c.id, "0.10")
    create_refund(store, gw, c.id, "0.20")
    assert sum(r.amount_cents for r in refunds_for_charge(store, c.id)) == 30


def test_19_99(store, charge):
    from payouts import ledger

    create_refund(store, FakeGateway(store, faults=[]), charge.id, "19.99")
    assert ledger.balance(store, charge.merchant_id) == 5000 - 1999


def test_jpy_refund(store):
    m = create_merchant(store, "Tokyo Tea", currency="JPY", fee_bps=0, fee_fixed_cents=0)
    gw = FakeGateway(store, faults=[])
    c = create_charge(store, gw, m.id, 5000)
    assert create_refund(store, gw, c.id, "500").amount_cents == 500
    with pytest.raises(RefundError):
        create_refund(store, gw, c.id, "12.5")


def test_lost_response_refunds_once(store, charge):
    gw = FakeGateway(store, faults=[("refund", "lost")])
    create_refund(store, gw, charge.id, "5.00")
    assert len([op for op in gw.operations() if op["op"] == "refund"]) == 1
    assert len(refunds_for_charge(store, charge.id)) == 1


def test_voided_charge_not_refundable(store, charge):
    from payouts.charges import void_charge

    gw = FakeGateway(store, faults=[])
    void_charge(store, gw, charge.id)
    with pytest.raises(RefundError, match="voided"):
        create_refund(store, gw, charge.id, "1.00")


def test_refund_after_payout_carries_shortfall(store, charge):
    from payouts import ledger
    from payouts.payout import create_payout
    from payouts.statements import build_statement, render

    gw = FakeGateway(store, faults=[])
    create_payout(store, gw, charge.merchant_id)
    create_refund(store, gw, charge.id, "20.00")
    text = render(build_statement(store, charge.merchant_id))
    assert "Carried to next payout: -20.00" in text
    assert text.endswith("Balance: 0.00")
    create_charge(store, gw, charge.merchant_id, 10000)
    assert create_payout(store, gw, charge.merchant_id).amount_cents == 8000
    assert ledger.balance(store, charge.merchant_id) == 0
