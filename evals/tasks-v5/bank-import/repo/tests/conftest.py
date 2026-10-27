import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from pennywise.store import Store

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def store(tmp_path):
    s = Store.open(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def cli(tmp_path):
    db = tmp_path / "cli.db"

    def run(*args, check=True):
        env = dict(os.environ, PENNYWISE_DB=str(db), PENNYWISE_TODAY="2025-09-01",
                   PYTHONPATH=str(ROOT))
        proc = subprocess.run([sys.executable, "-m", "pennywise", *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=60)
        if check:
            assert proc.returncode == 0, proc.stderr
        return proc

    run.json = lambda *args: json.loads(run(*args, "--json").stdout)
    return run


def d(text):
    return date.fromisoformat(text)
