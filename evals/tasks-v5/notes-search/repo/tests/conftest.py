import os
import subprocess
import sys
from pathlib import Path

import pytest

from jotter.store import Store

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "vault"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("JOTTER_NOW", "2026-05-01T10:00:00")
    return Store(tmp_path / "vault")


@pytest.fixture
def sample():
    return Store(SAMPLE)


def write_note(root, name, text):
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def jotter(tmp_path):
    def run(*args, vault=None, stdin=None):
        env = dict(os.environ, JOTTER_VAULT=str(vault or tmp_path / "vault"),
                   JOTTER_NOW="2026-05-01T10:00:00", PYTHONPATH=str(ROOT))
        proc = subprocess.run([sys.executable, "-m", "jotter", *args], cwd=tmp_path, env=env,
                              input=stdin, capture_output=True, text=True, timeout=30)
        return proc
    return run
