import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(data_dir, *args):
    proc = subprocess.run([sys.executable, "-m", "meterly", "--data", str(data_dir), *args],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_customers(data_dir):
    out = run(data_dir, "customers")
    assert "cus_sakura" in out and "Asia/Tokyo" in out
    assert "priority-support" in out


def test_plans(data_dir):
    out = run(data_dir, "plans")
    assert "legacy_usd (retired)" in out
    assert "first 5,000 units included" in out


def test_quote(data_dir):
    out = run(data_dir, "quote", "20000", "--currency", "GBP")
    assert "starter_gbp" in out and "pro_gbp" in out


def test_activity(data_dir):
    assert "calls" in run(data_dir, "activity", "--month", "2026-09")


def test_history_and_tax(data_dir):
    assert "pro_gbp" in run(data_dir, "history", "cus_harbour")
    assert "VAT 19%" in run(data_dir, "tax", "cus_lindgren")
