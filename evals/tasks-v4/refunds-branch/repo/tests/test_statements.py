from payouts.charges import create_charge
from payouts.gateway import FakeGateway
from payouts.merchants import create_merchant
from payouts.payout import create_payout
from payouts.statements import build_statement, render


def test_statement_lines_and_balance(store):
    m = create_merchant(store, "Acme")
    gw = FakeGateway(store, faults=[])
    create_charge(store, gw, m.id, 10000, "order 1")
    create_payout(store, gw, m.id, 5000)
    st = build_statement(store, m.id)
    assert [line.label for line in st.lines] == ["Charge", "Fee", "Payout"]
    assert st.balance_cents == 10000 - 320 - 5000
    text = render(st)
    assert "Statement for Acme (m_0001)" in text
    assert "-3.20" in text
    assert "-50.00" in text
    assert text.splitlines()[-1] == "Balance: 46.80"


def test_empty_statement(store):
    m = create_merchant(store, "Quiet")
    text = render(build_statement(store, m.id))
    assert "(no activity)" in text
    assert text.endswith("Balance: 0.00")


def test_long_memo_truncated(store):
    m = create_merchant(store, "Acme", fee_bps=0, fee_fixed_cents=0)
    create_charge(store, FakeGateway(store, faults=[]), m.id, 100, "x" * 80)
    assert "x" * 28 + "..." in render(build_statement(store, m.id))
