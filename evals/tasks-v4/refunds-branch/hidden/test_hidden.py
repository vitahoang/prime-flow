"""Acceptance tests for `python -m payouts refund CHARGE_ID AMOUNT [--reason ...]`
and refunds on `python -m payouts statement MERCHANT_ID`. CLI only."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


@pytest.fixture
def cli(tmp_path):
    base = {k: v for k, v in os.environ.items() if not k.startswith("PAYOUTS_")}
    base["PAYOUTS_DATA_DIR"] = str(tmp_path / "data")

    def run(*args, faults=None):
        env = dict(base)
        if faults:
            env["PAYOUTS_GATEWAY_FAULTS"] = faults
        return subprocess.run(
            [sys.executable, "-m", "payouts", *args],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
        )

    return run


def merchant(cli, name="Bean There", currency=None):
    extra = ["--currency", currency] if currency else []
    out = cli("merchant", "add", name, "--fee-bps", "0", "--fee-fixed-cents", "0", *extra)
    assert out.returncode == 0, out.stderr
    return re.search(r"\bm_\w+", out.stdout).group(0)


def charge(cli, m, amount):
    out = cli("charge", m, amount, "--description", "order")
    assert out.returncode == 0, out.stderr
    return re.search(r"\bch_\w+", out.stdout).group(0)


def refund(cli, ch, amount, *extra, faults=None):
    return cli("refund", ch, amount, *extra, faults=faults)


def balance(cli, m):
    out = cli("statement", m)
    assert out.returncode == 0, out.stderr
    found = re.findall(r"balance\W*(-?[$¥]?-?[\d,]+(?:\.\d\d)?)\b", out.stdout, re.I)
    assert found, out.stdout
    return found[-1].replace("$", "").replace("¥", "").replace(",", "")


def gateway_refunds(cli):
    out = cli("gateway-log")
    assert out.returncode == 0, out.stderr
    return [line for line in out.stdout.splitlines() if line.split("\t")[0] == "refund"]


def gateway_payouts(cli):
    out = cli("gateway-log")
    return [line.split("\t") for line in out.stdout.splitlines() if line.split("\t")[0] == "payout"]


def refund_lines(cli, m):
    out = cli("statement", m)
    return [line for line in out.stdout.splitlines() if "refund" in line.lower()]


# --- explicit ---------------------------------------------------------------

def test_E1_refund_command_succeeds(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    out = refund(cli, ch, "10.00", "--reason", "damaged in transit")
    assert out.returncode == 0, out.stderr
    assert len(gateway_refunds(cli)) == 1


def test_E1_refund_more_than_charge_rejected(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    out = refund(cli, ch, "60.00")
    assert out.returncode != 0
    assert "invalid choice" not in out.stderr
    assert gateway_refunds(cli) == []
    assert refund(cli, ch, "50.00").returncode == 0


def test_E1_refund_unknown_charge_rejected(cli):
    merchant(cli)
    out = refund(cli, "ch_9999", "1.00")
    assert out.returncode != 0
    assert "invalid choice" not in out.stderr
    assert "Traceback" not in out.stderr


def test_E2_statement_shows_negative_refund_line(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert refund(cli, ch, "10.00").returncode == 0
    lines = refund_lines(cli, m)
    assert any(re.search(r"-\s*\$?10\.00\b", line) for line in lines), lines


def test_E2_balance_drops_by_refund(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert balance(cli, m) == "50.00"
    assert refund(cli, ch, "10.00").returncode == 0
    assert balance(cli, m) == "40.00"


# --- T1: exact cents ----------------------------------------------------------

def test_T1_full_refund_of_19_99_zeroes_balance(cli):
    m = merchant(cli)
    ch = charge(cli, m, "19.99")
    assert refund(cli, ch, "19.99").returncode == 0
    assert balance(cli, m) == "0.00"
    assert any(re.search(r"-\s*\$?19\.99\b", line) for line in refund_lines(cli, m))


def test_T1_small_refunds_add_up_exactly(cli):
    m = merchant(cli)
    ch = charge(cli, m, "100.00")
    for amount in ("0.29", "0.57", "1.15"):
        assert refund(cli, ch, amount).returncode == 0, amount
    assert balance(cli, m) == "97.99"


def test_T1_ten_plus_twenty_cents_is_thirty(cli):
    m = merchant(cli)
    ch = charge(cli, m, "0.30")
    assert refund(cli, ch, "0.10").returncode == 0
    out = refund(cli, ch, "0.20")
    assert out.returncode == 0, out.stderr
    assert balance(cli, m) == "0.00"


# --- T2: a timeout never refunds twice ----------------------------------------

def test_T2_lost_response_refunds_once(cli):
    m = merchant(cli)
    ch = charge(cli, m, "100.00")
    out = refund(cli, ch, "25.00", faults="refund:lost")
    assert out.returncode == 0, out.stderr
    assert len(gateway_refunds(cli)) == 1
    assert balance(cli, m) == "75.00"


def test_T2_two_lost_responses_still_once(cli):
    m = merchant(cli)
    ch = charge(cli, m, "100.00")
    out = refund(cli, ch, "40.00", faults="refund:lost,refund:lost")
    assert out.returncode == 0, out.stderr
    assert len(gateway_refunds(cli)) == 1
    assert balance(cli, m) == "60.00"


def test_T2_plain_timeout_then_success(cli):
    m = merchant(cli)
    ch = charge(cli, m, "100.00")
    out = refund(cli, ch, "10.00", faults="refund:timeout")
    assert out.returncode == 0, out.stderr
    assert len(gateway_refunds(cli)) == 1
    assert balance(cli, m) == "90.00"


# --- T3: cumulative refunds never exceed the charge -----------------------------

def test_T3_second_partial_over_total_rejected(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert refund(cli, ch, "30.00").returncode == 0
    out = refund(cli, ch, "30.00")
    assert out.returncode != 0
    assert len(gateway_refunds(cli)) == 1
    assert balance(cli, m) == "20.00"


def test_T3_nothing_left_after_full_refund(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert refund(cli, ch, "50.00").returncode == 0
    out = refund(cli, ch, "0.01")
    assert out.returncode != 0
    assert balance(cli, m) == "0.00"


def test_T3_interleaved_refunds_on_two_charges(cli):
    m = merchant(cli)
    a = charge(cli, m, "50.00")
    b = charge(cli, m, "50.00")
    assert refund(cli, a, "30.00").returncode == 0
    assert refund(cli, b, "5.00").returncode == 0
    assert refund(cli, a, "10.00").returncode == 0
    out = refund(cli, a, "20.00")
    assert out.returncode != 0
    assert len(gateway_refunds(cli)) == 3
    assert balance(cli, m) == "55.00"


def test_T3_full_refund_split_around_another_charge(cli):
    m = merchant(cli)
    a = charge(cli, m, "50.00")
    b = charge(cli, m, "20.00")
    assert refund(cli, a, "25.00").returncode == 0
    assert refund(cli, b, "5.00").returncode == 0
    assert refund(cli, a, "25.00").returncode == 0
    assert refund(cli, a, "0.01").returncode != 0
    assert balance(cli, m) == "15.00"


def test_T3_partials_up_to_exact_total_allowed(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert refund(cli, ch, "20.00").returncode == 0
    assert refund(cli, ch, "30.00").returncode == 0
    assert refund(cli, ch, "0.01").returncode != 0
    assert balance(cli, m) == "0.00"


# --- T4: refunds in the charge's currency (JPY has no decimals) -----------------

def test_T4_jpy_partial_refund(cli):
    m = merchant(cli, "Tokyo Tea", currency="JPY")
    ch = charge(cli, m, "5000")
    out = refund(cli, ch, "500")
    assert out.returncode == 0, out.stderr
    assert balance(cli, m) == "4500"
    assert [line.split("\t")[3] for line in gateway_refunds(cli)] == ["500"]


def test_T4_jpy_small_refund_not_multiplied(cli):
    m = merchant(cli, "Tokyo Tea", currency="JPY")
    ch = charge(cli, m, "5000")
    assert refund(cli, ch, "50").returncode == 0
    assert balance(cli, m) == "4950"


def test_T4_jpy_fraction_rejected(cli):
    m = merchant(cli, "Tokyo Tea", currency="JPY")
    ch = charge(cli, m, "5000")
    out = refund(cli, ch, "12.5")
    assert out.returncode != 0
    assert "invalid choice" not in out.stderr
    assert gateway_refunds(cli) == []


# --- H1: refund after payout: shortfall carried to the next payout --------------

def test_H1_refund_after_payout_goes_through_and_is_carried(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert cli("payout", m).returncode == 0
    out = refund(cli, ch, "20.00")
    assert out.returncode == 0, out.stderr
    assert len(gateway_refunds(cli)) == 1
    assert not balance(cli, m).startswith("-")
    st = cli("statement", m).stdout
    assert re.search(r"carr(y|ied)|next payout", st, re.I), st


def test_H1_next_payout_reduced_by_shortfall(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert cli("payout", m).returncode == 0
    assert refund(cli, ch, "20.00").returncode == 0
    charge(cli, m, "100.00")
    out = cli("payout", m)
    assert out.returncode == 0, out.stderr
    assert gateway_payouts(cli)[-1][3] == "8000"
    assert balance(cli, m) == "0.00"


def test_H1_partial_payout_then_refund(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert cli("payout", m, "40.00").returncode == 0
    assert refund(cli, ch, "30.00").returncode == 0
    assert not balance(cli, m).startswith("-")
    charge(cli, m, "25.00")
    assert cli("payout", m).returncode == 0
    assert gateway_payouts(cli)[-1][3] == "500"


# --- T5: main's voids (landed after Priya branched) ------------------------------

def test_T5_voided_charge_cannot_be_refunded(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    assert cli("void", ch).returncode == 0
    out = refund(cli, ch, "10.00")
    assert out.returncode != 0
    assert "invalid choice" not in out.stderr
    assert gateway_refunds(cli) == []
    assert balance(cli, m) == "0.00"


def test_T5_voided_charge_full_refund_rejected(cli):
    m = merchant(cli)
    ch = charge(cli, m, "50.00")
    other = charge(cli, m, "30.00")
    assert cli("void", ch).returncode == 0
    assert refund(cli, ch, "50.00").returncode != 0
    assert refund(cli, other, "10.00").returncode == 0
    assert balance(cli, m) == "20.00"
