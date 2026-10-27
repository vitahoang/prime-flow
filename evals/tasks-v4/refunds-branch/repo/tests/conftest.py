import pytest

from payouts.store import Store


@pytest.fixture(autouse=True)
def _no_faults(monkeypatch):
    monkeypatch.delenv("PAYOUTS_GATEWAY_FAULTS", raising=False)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)
