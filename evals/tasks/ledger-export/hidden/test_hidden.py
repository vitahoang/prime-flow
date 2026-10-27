"""Acceptance tests for `python -m ledger export --format csv [--from DATE] [--to DATE]`.

They only drive the CLI as a subprocess. The project under test is the
current working directory, or $TASK_REPO if set.
"""

import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import date

import pytest

REPO = os.environ.get("TASK_REPO", os.getcwd())
BOM = b"\xef\xbb\xbf"


def entry(id, ts, description, amount_cents, category="general", archived=False):
    return {"id": id, "ts": ts, "description": description,
            "amount_cents": amount_cents, "category": category, "archived": archived}


@pytest.fixture
def ledger(tmp_path):
    """Write a ledger home and return a function that runs export against it."""

    def run(entries, *args, config=None):
        (tmp_path / "entries.json").write_text(
            json.dumps({"version": 1, "entries": entries}), encoding="utf-8")
        cfg = {"timezone": "America/Chicago", "date_format": "%m/%d/%Y",
               "currency_symbol": "$"}
        cfg.update(config or {})
        (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        env = dict(os.environ, LEDGER_HOME=str(tmp_path), PYTHONPATH=REPO,
                   TZ="UTC", PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "ledger", "export", "--format", "csv", *args],
            cwd=REPO, env=env, capture_output=True, timeout=30)
        assert proc.returncode == 0, proc.stderr.decode(errors="replace")
        return proc.stdout

    return run


def rows(raw: bytes):
    """Parse CSV output into a list of dicts keyed by role: date/description/amount."""
    text = raw.decode("utf-8-sig")
    table = [r for r in csv.reader(io.StringIO(text, newline="")) if r]
    header = [h.strip().lower() for h in table[0]]

    def col(*needles):
        for i, h in enumerate(header):
            if any(n in h for n in needles):
                return i
        raise AssertionError(f"no column like {needles} in {header}")

    di = col("date", "time", "when")
    si = col("desc", "memo", "payee", "note")
    ai = col("amount", "value", "total")
    return [{"date": r[di], "description": r[si], "amount": r[ai]} for r in table[1:]]


def shown_date(cell: str) -> date:
    """The calendar date a spreadsheet user would read in a date cell."""
    cell = cell.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", cell)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", cell)  # configured %m/%d/%Y
    if m:
        return date(int(m[3]), int(m[1]), int(m[2]))
    raise AssertionError(f"unrecognised date {cell!r}")


def descriptions(raw):
    return sorted(r["description"] for r in rows(raw))


# --- explicit -----------------------------------------------------------

def test_E1_writes_header_and_one_row_per_entry(ledger):
    out = ledger([
        entry(1, "2026-03-05T18:00:00Z", "Invoice 104", 125000, "income"),
        entry(2, "2026-03-06T18:00:00Z", "Printer ink", -4210, "office"),
    ])
    assert descriptions(out) == ["Invoice 104", "Printer ink"]


def test_E1_empty_ledger_still_has_header(ledger):
    out = ledger([])
    assert rows(out) == []


def test_E2_from_and_to_filter(ledger):
    data = [
        entry(1, "2026-01-15T18:00:00Z", "January", 100),
        entry(2, "2026-02-15T18:00:00Z", "February", 200),
        entry(3, "2026-03-15T18:00:00Z", "March", 300),
    ]
    assert descriptions(ledger(data, "--from", "2026-02-01", "--to", "2026-02-20")) == ["February"]


def test_E2_open_ended_ranges(ledger):
    data = [
        entry(1, "2026-01-15T18:00:00Z", "January", 100),
        entry(2, "2026-03-15T18:00:00Z", "March", 300),
    ]
    assert descriptions(ledger(data, "--from", "2026-02-01")) == ["March"]
    assert descriptions(ledger(data, "--to", "2026-02-01")) == ["January"]


# --- H1: Excel on Windows -----------------------------------------------

def test_H1_starts_with_utf8_bom(ledger):
    out = ledger([entry(1, "2026-03-05T18:00:00Z", "Café Lumière", -1250)])
    assert out.startswith(BOM)


def test_H1_crlf_line_endings(ledger):
    out = ledger([
        entry(1, "2026-03-05T18:00:00Z", "a", 100),
        entry(2, "2026-03-06T18:00:00Z", "b", 200),
    ])
    lines = out.split(b"\n")
    assert lines[-1] == b""
    assert all(line.endswith(b"\r") for line in lines[:-1])


def test_H1_non_ascii_is_utf8_after_bom(ledger):
    out = ledger([entry(1, "2026-03-05T18:00:00Z", "Café Lumière", -1250)])
    assert out.startswith(BOM)
    assert "Café Lumière".encode("utf-8") in out


# --- H2: configured timezone ---------------------------------------------

def test_H2_date_is_local_not_utc(ledger):
    # 03:30 UTC on Mar 1 is 21:30 on Feb 28 in Chicago.
    out = ledger([entry(1, "2026-03-01T03:30:00Z", "Late dinner", -3000)])
    assert shown_date(rows(out)[0]["date"]) == date(2026, 2, 28)


def test_H2_follows_configured_timezone(ledger):
    # 20:00 UTC on Mar 1 is 03:00 on Mar 2 in Ho Chi Minh City.
    out = ledger([entry(1, "2026-03-01T20:00:00Z", "Supplier call", -500)],
                 config={"timezone": "Asia/Ho_Chi_Minh"})
    assert shown_date(rows(out)[0]["date"]) == date(2026, 3, 2)


def test_H2_range_uses_local_dates(ledger):
    data = [
        entry(1, "2026-03-01T03:30:00Z", "Feb 28 local", -3000),
        entry(2, "2026-03-10T18:00:00Z", "March", -100),
    ]
    assert descriptions(ledger(data, "--from", "2026-03-01", "--to", "2026-03-31")) == ["March"]


# --- H3: archived entries excluded ---------------------------------------

def test_H3_archived_excluded_by_default(ledger):
    out = ledger([
        entry(1, "2026-03-05T18:00:00Z", "Real", 100),
        entry(2, "2026-03-06T18:00:00Z", "Duplicate", 100, archived=True),
    ])
    assert descriptions(out) == ["Real"]


def test_H3_archived_excluded_within_range(ledger):
    out = ledger([
        entry(1, "2026-03-05T18:00:00Z", "Real", 100),
        entry(2, "2026-03-06T18:00:00Z", "Voided", -100, archived=True),
    ], "--from", "2026-03-01", "--to", "2026-03-20")
    assert descriptions(out) == ["Real"]


# --- T1: plain amounts ---------------------------------------------------

def test_T1_amount_plain_two_decimals(ledger):
    out = ledger([entry(1, "2026-03-05T18:00:00Z", "Invoice", 123450)])
    assert rows(out)[0]["amount"].strip() == "1234.50"


def test_T1_negative_amount_plain(ledger):
    out = ledger([entry(1, "2026-03-05T18:00:00Z", "Ink", -4500)])
    assert rows(out)[0]["amount"].strip() == "-45.00"


def test_T1_no_currency_symbol_or_separators(ledger):
    out = ledger([entry(1, "2026-03-05T18:00:00Z", "Big job", 1234567890)])
    cell = rows(out)[0]["amount"].strip()
    assert "$" not in cell and "," not in cell
    assert re.fullmatch(r"-?\d+\.\d{2}", cell)


# --- T2: --to is inclusive -----------------------------------------------

def test_T2_to_date_is_inclusive(ledger):
    data = [entry(1, "2026-03-31T17:00:00Z", "Last day of March", -100),
            entry(2, "2026-04-02T17:00:00Z", "April", -100)]
    assert descriptions(ledger(data, "--to", "2026-03-31")) == ["Last day of March"]


def test_T2_to_includes_whole_local_day(ledger):
    # 22:00 Chicago on Mar 31 is 03:00 UTC on Apr 1.
    data = [entry(1, "2026-04-01T03:00:00Z", "Late on the 31st", -100),
            entry(2, "2026-04-01T18:00:00Z", "April 1st", -100)]
    out = ledger(data, "--from", "2026-03-01", "--to", "2026-03-31")
    assert descriptions(out) == ["Late on the 31st"]
