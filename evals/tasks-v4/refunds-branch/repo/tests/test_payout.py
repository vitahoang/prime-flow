import pytest

from payouts import ledger
from payouts.charges import create_charge
from payouts.errors import InsufficientFunds, ValidationError
from payouts.gateway import FakeGateway
from payouts.merchants import create_merchant
from payouts.payout import create_payout


@pytest.fixture
def funded(store):
    m = create_merchant(store, "Acme", fee_bps=0, fee_fixed_cents=0)
    create_charge(store, FakeGateway(store, faults=[]), m.id, 5000)
    return m


def test_payout_whole_balance(store, funded):
    p = create_payout(store, FakeGateway(store, faults=[]), funded.id)
    assert p.amount_cents == 5000
    assert ledger.balance(store, funded.id) == 0


def test_partial_payout(store, funded):
    create_payout(store, FakeGateway(store, faults=[]), funded.id, 2000)
    assert ledger.balance(store, funded.id) == 3000


def test_cannot_overdraw(store, funded):
    with pytest.raises(InsufficientFunds):
        create_payout(store, FakeGateway(store, faults=[]), funded.id, 5001)


def test_minimum(store, funded):
    with pytest.raises(ValidationError):
        create_payout(store, FakeGateway(store, faults=[]), funded.id, 99)
