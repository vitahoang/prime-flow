import shutil
from pathlib import Path

import pytest

from meterly import store as store_mod

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "data"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    target = tmp_path / "data"
    shutil.copytree(EXAMPLES, target)
    monkeypatch.setenv("METERLY_DATA", str(target))
    return target


@pytest.fixture
def store(data_dir):
    return store_mod.load(data_dir)
