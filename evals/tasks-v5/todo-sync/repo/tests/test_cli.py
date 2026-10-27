import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(tmp_path, *args):
    env = dict(os.environ, TICKOFF_HOME=str(tmp_path), TICKOFF_DEVICE="laptop",
               TICKOFF_TODAY="2026-10-20", PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-m", "tickoff", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=30)
    return proc


def test_add_ls_done(tmp_path):
    assert run(tmp_path, "add", "Buy", "stamps", "--list", "errands", "--due", "tomorrow").returncode == 0
    run(tmp_path, "add", "Call the bank", "--list", "errands", "--at", "0")
    out = run(tmp_path, "ls").stdout
    assert out.index("Call the bank") < out.index("Buy stamps")
    assert "(tomorrow)" in out
    assert run(tmp_path, "done", "Buy stamps").returncode == 0
    assert "Buy stamps" not in run(tmp_path, "ls").stdout
    assert "Buy stamps" in run(tmp_path, "ls", "--all").stdout
    assert (tmp_path / "laptop.json").exists()


def test_errors_exit_1(tmp_path):
    proc = run(tmp_path, "done", "nothing")
    assert proc.returncode == 1
    assert "no such task" in proc.stderr
    assert run(tmp_path, "add", "x", "--due", "someday").returncode == 1


def test_history_and_export(tmp_path):
    run(tmp_path, "add", "Water the ferns")
    run(tmp_path, "edit", "Water the ferns", "--title", "Water the ferns and the basil")
    out = run(tmp_path, "history", "Water the ferns and the basil").stdout
    assert "created 'Water the ferns'" in out
    assert "- [ ] Water the ferns and the basil" in run(tmp_path, "export").stdout
