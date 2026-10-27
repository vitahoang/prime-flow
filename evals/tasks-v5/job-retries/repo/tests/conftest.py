import pytest

from taskmill.clock import FakeClock
from taskmill.registry import Registry
from taskmill.store import JobStore


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(tmp_path):
    s = JobStore(tmp_path / "jobs.db")
    yield s
    s.close()


@pytest.fixture
def registry():
    return Registry()


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch, tmp_path):
    # Never pick up the repo's production config.toml from the cwd.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TASKMILL_CONFIG", raising=False)
    monkeypatch.delenv("TASKMILL_DB", raising=False)
