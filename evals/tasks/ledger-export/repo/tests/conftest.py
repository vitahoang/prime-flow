import json

import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def write_entries(home):
    def write(entries, config=None):
        (home / "entries.json").write_text(
            json.dumps({"version": 1, "entries": entries}), encoding="utf-8"
        )
        if config is not None:
            (home / "config.json").write_text(json.dumps(config), encoding="utf-8")

    return write
