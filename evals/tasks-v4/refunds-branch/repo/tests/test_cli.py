import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cli(tmp_path, monkeypatch):
    env = {"PATH": "/usr/bin:/bin", "PAYOUTS_DATA_DIR": str(tmp_path / "data")}

    def run(*args, faults=None):
        e = dict(env)
        if faults:
            e["PAYOUTS_GATEWAY_FAULTS"] = faults
        return subprocess.run(
            [sys.executable, "-m", "payouts", *args], cwd=ROOT, env=e, capture_output=True, text=True
        )

    return run


def test_merchant_charge_statement(cli):
    m = cli("merchant", "add", "Acme").stdout.strip()
    assert m == "m_0001"
    out = cli("charge", m, "100.00", "--description", "order 1")
    assert out.returncode == 0, out.stderr
    assert re.match(r"ch_0001 charged 100\.00 USD \(fee 3\.20\)", out.stdout)
    st = cli("statement", m)
    assert st.returncode == 0
    assert st.stdout.strip().splitlines()[-1] == "Balance: 96.80"


def test_bad_amount(cli):
    m = cli("merchant", "add", "Acme").stdout.strip()
    out = cli("charge", m, "12.345")
    assert out.returncode == 1
    assert "decimal places" in out.stderr


def test_jpy_merchant(cli):
    m = cli("merchant", "add", "Tokyo Tea", "--currency", "JPY", "--fee-bps", "0", "--fee-fixed-cents", "0").stdout.strip()
    out = cli("charge", m, "5000")
    assert out.returncode == 0, out.stderr
    assert "charged 5000 JPY" in out.stdout
    assert cli("statement", m).stdout.strip().endswith("Balance: 5000")
    assert cli("gateway-log").stdout.split("\t")[3].strip() == "5000"
    assert cli("charge", m, "12.50").returncode == 1


def test_unknown_merchant(cli):
    out = cli("statement", "m_0404")
    assert out.returncode == 1
    assert "no merchant" in out.stderr


def test_payout(cli):
    m = cli("merchant", "add", "Acme", "--fee-bps", "0", "--fee-fixed-cents", "0").stdout.strip()
    cli("charge", m, "20.00")
    out = cli("payout", m, "5.00")
    assert out.returncode == 0, out.stderr
    assert cli("statement", m).stdout.strip().endswith("Balance: 15.00")


def test_gateway_log(cli):
    m = cli("merchant", "add", "Acme").stdout.strip()
    cli("charge", m, "20.00", faults="charge:timeout")
    lines = cli("gateway-log").stdout.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].split("\t")[0] == "charge"
    assert lines[0].split("\t")[3] == "2000"
