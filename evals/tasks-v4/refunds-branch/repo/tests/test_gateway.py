import pytest

from payouts.gateway import FakeGateway, GatewayDeclined, GatewayTimeout, call_with_retries


def test_charge_records_operation(store):
    gw = FakeGateway(store, faults=[])
    result = gw.charge(1000, "x")
    assert result["ref"].startswith("gw_ch_")
    assert [op["ref"] for op in gw.operations()] == [result["ref"]]


def test_state_shared_between_instances(store):
    FakeGateway(store, faults=[]).charge(1000, "x")
    assert len(FakeGateway(store, faults=[]).operations()) == 1


def test_timeout_fault_commits_nothing(store):
    gw = FakeGateway(store, faults=[("charge", "timeout")])
    with pytest.raises(GatewayTimeout):
        gw.charge(1000, "x")
    assert gw.operations() == []
    gw.charge(1000, "x")
    assert len(gw.operations()) == 1


def test_decline_fault(store):
    gw = FakeGateway(store, faults=[("charge", "decline")])
    with pytest.raises(GatewayDeclined):
        gw.charge(1000, "x")


def test_faults_are_per_operation(store):
    gw = FakeGateway(store, faults=[("payout", "timeout")])
    gw.charge(1000, "x")
    with pytest.raises(GatewayTimeout):
        gw.payout("m_0001", 500)


def test_faults_from_env(store, monkeypatch):
    monkeypatch.setenv("PAYOUTS_GATEWAY_FAULTS", "charge:timeout, charge:decline")
    gw = FakeGateway(store)
    with pytest.raises(GatewayTimeout):
        gw.charge(1000, "x")
    with pytest.raises(GatewayDeclined):
        gw.charge(1000, "x")
    gw.charge(1000, "x")


def test_unknown_fault_rejected(store):
    with pytest.raises(ValueError):
        FakeGateway(store, faults=[("charge", "explode")])


def test_retries_until_success():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise GatewayTimeout("slow")
        return "ok"

    assert call_with_retries(flaky, attempts=3) == "ok"
    assert len(calls) == 3


def test_retries_give_up():
    def always():
        raise GatewayTimeout("slow")

    with pytest.raises(GatewayTimeout):
        call_with_retries(always, attempts=2)


def test_declines_not_retried():
    calls = []

    def declined():
        calls.append(1)
        raise GatewayDeclined("no")

    with pytest.raises(GatewayDeclined):
        call_with_retries(declined)
    assert len(calls) == 1


def test_lost_response_commits_but_times_out(store):
    gw = FakeGateway(store, faults=[("charge", "lost")])
    with pytest.raises(GatewayTimeout):
        gw.charge(1000, "x")
    assert len(gw.operations()) == 1


def test_idempotency_key_replays(store):
    gw = FakeGateway(store, faults=[("charge", "lost")])
    with pytest.raises(GatewayTimeout):
        gw.charge(1000, "x", idempotency_key="k1")
    again = gw.charge(1000, "x", idempotency_key="k1")
    assert len(gw.operations()) == 1
    assert again["ref"] == gw.operations()[0]["ref"]
