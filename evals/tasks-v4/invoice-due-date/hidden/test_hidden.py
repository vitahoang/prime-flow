"""Acceptance tests for the due-date fix. They drive only `python -m invoicer`
(show, reminders [--on/--send], overdue, statement, list) with a fixture data
directory in INVOICER_DATA_DIR and a pinned clock in INVOICER_NOW. The daily
run in this repo is `overdue` then `reminders --send`."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

CUSTOMERS = [
    {"id": "C001", "name": "Lim & Tan Pte Ltd", "email": "a@x", "timezone": "Asia/Singapore", "currency": "SGD"},
    {"id": "C002", "name": "Harbourside Dental", "email": "b@x", "timezone": "Australia/Sydney", "currency": "AUD"},
    {"id": "C003", "name": "Brightline Media", "email": "c@x", "timezone": "America/Los_Angeles", "currency": "USD"},
    {"id": "C004", "name": "Kai Surf Co", "email": "d@x", "timezone": "Pacific/Honolulu", "currency": "USD"},
    {"id": "C005", "name": "Northgate Books", "email": "e@x", "timezone": "Europe/London", "currency": "GBP"},
    {"id": "C006", "name": "Mehta Analytics", "email": "f@x", "timezone": "Asia/Kolkata", "currency": "INR"},
    {"id": "C007", "name": "Torrens Wine Co", "email": "g@x", "timezone": "Australia/Adelaide", "currency": "AUD"},
    {"id": "C011", "name": "Marina Bay Florists", "email": "h@x", "timezone": "Asia/Singapore", "currency": "SGD"},
    {"id": "C012", "name": "Harbour Physio", "email": "i@x", "timezone": "Australia/Sydney", "currency": "AUD"},
    {"id": "C021", "name": "Tiong Bahru Bakery", "email": "j@x", "timezone": "Asia/Singapore", "currency": "SGD"},
    {"id": "C022", "name": "Bondi Yoga", "email": "k@x", "timezone": "Australia/Sydney", "currency": "AUD"},
]


def _inv(id, customer, terms, currency, amount, **issued):
    row = {"id": id, "customer": customer, "terms": terms, "currency": currency,
           "lines": [{"description": "Design work", "quantity": 1, "unit_price": amount}]}
    row.update(issued)
    return row


INVOICES = [
    # Singapore, issued 01:30 local on 4 Sep -> due 4 Oct
    _inv("INV-2001", "C001", "Net 30", "SGD", "2000.00", issued_at="2026-09-03T17:30:00Z"),
    # Sydney, issued 01:00 local on 11 Sep -> due 11 Oct (AEDT by then)
    _inv("INV-2002", "C002", "Net 30", "AUD", "3000.00", issued_at="2026-09-10T15:00:00Z"),
    # Los Angeles, issued 09:00 local on 8 Sep -> due 8 Oct
    _inv("INV-2003", "C003", "Net 30", "USD", "1500.00", issued_at="2026-09-08T16:00:00Z"),
    # Los Angeles, issued 19:30 local on 8 Sep (already 9 Sep in UTC) -> due 8 Oct
    _inv("INV-2013", "C003", "Net 30", "USD", "900.00", issued_at="2026-09-09T02:30:00Z"),
    # Honolulu, issued 22:30 local on 14 Sep -> due 14 Oct
    _inv("INV-2004", "C004", "Net 30", "USD", "1400.00", issued_at="2026-09-15T08:30:00Z"),
    # London control
    _inv("INV-2005", "C005", "Net 30", "GBP", "1000.00", issued_at="2026-09-01T10:00:00Z"),
    # Kolkata (+05:30), issued 00:15 local on 2 Sep -> Net 15 -> due 17 Sep
    _inv("INV-2006", "C006", "Net 15", "INR", "185000.00", issued_at="2026-09-01T18:45:00Z"),
    # Adelaide, issued 00:30 ACDT on 5 Apr, the night DST ends -> due 5 May
    _inv("INV-2007", "C007", "Net 30", "AUD", "1950.00", issued_at="2026-04-04T14:00:00Z"),
    # Adelaide, issued 00:15 ACST on 4 Sep -> due 4 Oct, the day DST starts
    _inv("INV-2017", "C007", "Net 30", "AUD", "650.00", issued_at="2026-09-03T14:45:00Z"),
    # Sydney, same instant as INV-2002 but spelled with +00:00
    _inv("INV-2008", "C002", "Net 30", "AUD", "500.00", issued_at="2026-09-10T15:00:00+00:00"),
    # v0 records: plain dates, already the customer's own date
    _inv("INV-0901", "C002", "Net 30", "AUD", "4800.00", issued_on="2025-12-01"),
    _inv("INV-0902", "C003", "Net 15", "USD", "700.00", issued_on="2025-12-01"),
    # Damage already done by the bug (H4, H5):
    # Singapore, due 4 Oct; paid 18:00 SGT on 4 Oct, but a fee was charged at 15:00 SGT that day
    _inv("INV-2101", "C011", "Net 30", "SGD", "2000.00", issued_at="2026-09-03T17:30:00Z"),
    # Sydney, due 11 Oct; paid 20:00 AEDT on 11 Oct, but a fee was charged at 18:00 AEDT that day
    _inv("INV-2102", "C012", "Net 30", "AUD", "3000.00", issued_at="2026-09-10T15:00:00Z"),
    # Sydney, due 19 Sep, unpaid; its fee was charged correctly the next day
    _inv("INV-2112", "C012", "Net 30", "AUD", "1000.00", issued_at="2026-08-20T03:00:00Z"),
    # Unpaid twins of INV-2001 / INV-2002 whose 7-day reminders went out on the old dates
    _inv("INV-2201", "C021", "Net 30", "SGD", "800.00", issued_at="2026-09-03T17:30:00Z"),
    _inv("INV-2202", "C022", "Net 30", "AUD", "800.00", issued_at="2026-09-10T15:00:00Z"),
]

PAYMENTS = [
    {"invoice": "INV-2005", "amount": "100.00", "paid_at": "2026-09-20T09:00:00Z"},
    {"invoice": "INV-2101", "amount": "2000.00", "paid_at": "2026-10-04T10:00:00Z"},
    {"invoice": "INV-2102", "amount": "3000.00", "paid_at": "2026-10-11T09:00:00Z"},
]

FEES = [
    {"invoice": "INV-2112", "amount": "20.00", "charged_at": "2026-09-20T07:00:00Z"},
    {"invoice": "INV-2101", "amount": "40.00", "charged_at": "2026-10-04T07:00:00Z"},
    {"invoice": "INV-2102", "amount": "60.00", "charged_at": "2026-10-11T07:00:00Z"},
]

# Reminders sent on the old (one day early) dates: the 7-day ones.
SENT = [
    {"invoice": "INV-2201", "sent_on": "2026-09-26"},
    {"invoice": "INV-2202", "sent_on": "2026-10-03"},
]


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "customers.json").write_text(json.dumps({"customers": CUSTOMERS}, indent=2))
    (root / "invoices.json").write_text(json.dumps({"invoices": INVOICES}, indent=2))
    (root / "payments.json").write_text(json.dumps({"payments": PAYMENTS}, indent=2))
    (root / "fees.json").write_text(json.dumps({"fees": FEES}, indent=2))
    (root / "reminders_sent.json").write_text(json.dumps({"sent": SENT}, indent=2))
    return root


def cli(data, now, *args):
    env = dict(os.environ)
    env.update({
        "INVOICER_DATA_DIR": str(data),
        "INVOICER_NOW": now,
        "TZ": "Europe/London",
        "PYTHONPATH": str(ROOT),
    })
    proc = subprocess.run([sys.executable, "-m", "invoicer", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def due_shown(data, invoice_id, now="2026-09-20T00:00:00Z"):
    out = cli(data, now, "show", invoice_id)
    m = re.search(r"^\s*Due:?\s+(.+?)\s*$", out, re.M)
    assert m, out
    return m.group(1)


def status_shown(data, invoice_id, now):
    out = cli(data, now, "show", invoice_id)
    m = re.search(r"^\s*Status:?\s+(\w+)", out, re.M)
    assert m, out
    return m.group(1).upper(), out


def overdue_ids(data, now):
    out = cli(data, now, "overdue")
    return set(re.findall(r"\bINV-\d+\b", out)), out


ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def reminder_pairs(data, invoice_id, now="2026-09-20T00:00:00Z"):
    """{(send_on, due)} for one invoice from `reminders`."""
    out = cli(data, now, "reminders")
    pairs = set()
    for line in out.splitlines():
        if re.search(rf"\b{invoice_id}\b", line):
            found = ISO.findall(line)
            assert len(found) >= 2, line
            pairs.add((found[0], found[-1]))
    return pairs


def reminders_on(data, day, now="2026-09-20T00:00:00Z"):
    return set(re.findall(r"\bINV-\d+\b", cli(data, now, "reminders", "--on", day)))


# --- E: the reported problem --------------------------------------------------

def test_E1_singapore_due_date_shown(data):
    assert due_shown(data, "INV-2001") == "4 Oct 2026"


def test_E1_singapore_due_date_in_html(data):
    out = cli(data, "2026-09-20T00:00:00Z", "show", "INV-2001", "--html")
    assert "4 Oct 2026" in out
    assert "3 Oct 2026" not in out


def test_E2_sydney_due_date_shown(data):
    assert due_shown(data, "INV-2002") == "11 Oct 2026"


# --- H1: reminders use the customer's local due date ---------------------------

def test_H1_sydney_reminders_scheduled_from_local_due_date(data):
    assert reminder_pairs(data, "INV-2002") == {("2026-10-04", "2026-10-11"), ("2026-10-10", "2026-10-11")}


def test_H1_sydney_reminder_not_sent_a_day_early(data):
    assert "INV-2002" not in reminders_on(data, "2026-10-09")
    assert "INV-2002" in reminders_on(data, "2026-10-10")


def test_H1_singapore_reminders(data):
    assert reminder_pairs(data, "INV-2001") == {("2026-09-27", "2026-10-04"), ("2026-10-03", "2026-10-04")}


# --- H2: no overdue / late fee until the local due day is over -----------------

def test_H2_sydney_not_overdue_on_its_due_day(data):
    ids, out = overdue_ids(data, "2026-10-11T05:00:00Z")  # 16:00 on 11 Oct in Sydney
    assert "INV-2002" not in ids, out
    ids, out = overdue_ids(data, "2026-10-11T13:30:00Z")  # 00:30 on 12 Oct in Sydney
    assert "INV-2002" in ids, out


def test_H2_sydney_show_has_no_late_fee_on_due_day(data):
    status, out = status_shown(data, "INV-2002", "2026-10-11T05:00:00Z")
    assert status != "OVERDUE", out
    assert "late fee" not in out.lower(), out
    status, out = status_shown(data, "INV-2002", "2026-10-11T13:30:00Z")
    assert status == "OVERDUE", out
    assert "late fee" in out.lower(), out


def test_H2_singapore_not_overdue_on_its_due_day(data):
    ids, out = overdue_ids(data, "2026-10-04T03:00:00Z")  # 11:00 on 4 Oct in Singapore
    assert "INV-2001" not in ids, out
    ids, out = overdue_ids(data, "2026-10-04T16:30:00Z")  # 00:30 on 5 Oct
    assert "INV-2001" in ids, out


# --- H3: half-hour offsets and DST --------------------------------------------

def test_H3_kolkata_due_date_shown(data):
    assert due_shown(data, "INV-2006") == "17 Sep 2026"


def test_H3_kolkata_overdue_boundary(data):
    ids, out = overdue_ids(data, "2026-09-17T18:15:00Z")  # 23:45 IST on the due day
    assert "INV-2006" not in ids, out
    ids, out = overdue_ids(data, "2026-09-17T18:45:00Z")  # 00:15 IST next day
    assert "INV-2006" in ids, out


def test_H3_adelaide_issued_the_night_dst_ends(data):
    assert due_shown(data, "INV-2007") == "5 May 2026"


def test_H3_adelaide_overdue_on_the_day_dst_starts(data):
    ids, out = overdue_ids(data, "2026-10-04T13:15:00Z")  # 23:45 ACDT on 4 Oct
    assert "INV-2017" not in ids, out
    ids, out = overdue_ids(data, "2026-10-04T13:45:00Z")  # 00:15 ACDT on 5 Oct
    assert "INV-2017" in ids, out


def test_H3_adelaide_reminders(data):
    assert reminder_pairs(data, "INV-2017") == {("2026-09-27", "2026-10-04"), ("2026-10-03", "2026-10-04")}


# --- H4: fees already charged too early are reversed ---------------------------

def outstanding(data, now, customer_id, currency):
    out = cli(data, now, "statement", customer_id)
    m = re.search(rf"Total outstanding:?\s+{currency}\s+(-?[\d,]+\.\d\d)", out)
    assert m, out
    return m.group(1), out


def test_H4_sydney_fee_charged_on_due_day_is_reversed(data):
    now = "2026-10-19T07:00:00Z"
    cli(data, now, "overdue")
    total, out = outstanding(data, now, "C012", "AUD")
    # INV-2102 is paid and its 60.00 fee reversed; INV-2112 (1000 + its 20.00 fee) is still owed.
    assert total == "1,020.00", out


def test_H4_singapore_early_fee_reversed_and_original_kept(data):
    now = "2026-10-19T07:00:00Z"
    cli(data, now, "overdue")
    total, out = outstanding(data, now, "C011", "SGD")
    assert total == "0.00", out
    rows = json.loads((data / "fees.json").read_text())["fees"]
    for original in FEES:
        assert original in rows, "fee records must be reversed, not deleted or edited"


def test_H4_daily_runs_reverse_only_once_and_keep_correct_fees(data):
    for now in ("2026-10-19T07:00:00Z", "2026-10-20T07:00:00Z", "2026-10-21T07:00:00Z"):
        cli(data, now, "overdue")
        cli(data, now, "reminders", "--send")
    total, out = outstanding(data, "2026-10-21T08:00:00Z", "C012", "AUD")
    assert total == "1,020.00", out
    total, out = outstanding(data, "2026-10-21T08:00:00Z", "C011", "SGD")
    assert total == "0.00", out


# --- H5: reminders that already went out are not sent again --------------------

def test_H5_sydney_reminder_sent_on_old_date_not_sent_again(data):
    now = "2026-10-03T22:00:00Z"  # 09:00 on 4 Oct in Sydney: the corrected 7-day date
    out = cli(data, now, "reminders", "--send")
    assert "INV-2202" not in out, out
    assert reminder_pairs(data, "INV-2202", now=now) == {("2026-10-10", "2026-10-11")}


def test_H5_singapore_reminder_sent_on_old_date_not_listed_again(data):
    now = "2026-09-26T20:00:00Z"  # 04:00 on 27 Sep in Singapore
    assert "INV-2201" not in reminders_on(data, "2026-09-27", now=now)
    assert reminder_pairs(data, "INV-2201", now=now) == {("2026-10-03", "2026-10-04")}


# --- T1: customers west of UTC stay right --------------------------------------

def test_T1_los_angeles_due_dates_shown(data):
    assert due_shown(data, "INV-2003") == "8 Oct 2026"
    assert due_shown(data, "INV-2013") == "8 Oct 2026"


def test_T1_honolulu_due_date_shown(data):
    assert due_shown(data, "INV-2004") == "14 Oct 2026"


def test_T1_los_angeles_reminders(data):
    expected = {("2026-10-01", "2026-10-08"), ("2026-10-07", "2026-10-08")}
    assert reminder_pairs(data, "INV-2003") == expected
    assert reminder_pairs(data, "INV-2013") == expected


def test_T1_honolulu_overdue_boundary(data):
    ids, out = overdue_ids(data, "2026-10-15T09:30:00Z")  # 23:30 HST on 14 Oct
    assert "INV-2004" not in ids, out
    ids, out = overdue_ids(data, "2026-10-15T10:30:00Z")  # 00:30 HST on 15 Oct
    assert "INV-2004" in ids, out


def test_T1_los_angeles_evening_invoice_overdue_boundary(data):
    ids, out = overdue_ids(data, "2026-10-09T06:30:00Z")  # 23:30 PDT on 8 Oct
    assert "INV-2013" not in ids, out
    ids, out = overdue_ids(data, "2026-10-09T07:30:00Z")  # 00:30 PDT on 9 Oct
    assert "INV-2013" in ids, out


# --- T2: existing data is read as it is ----------------------------------------

def test_T2_v0_invoices_still_show(data):
    assert due_shown(data, "INV-0901", now="2025-12-10T00:00:00Z") == "31 Dec 2025"
    assert due_shown(data, "INV-0902", now="2025-12-10T00:00:00Z") == "16 Dec 2025"


def test_T2_v0_invoices_reminders_and_overdue(data):
    assert reminder_pairs(data, "INV-0902", now="2025-12-10T12:00:00Z") == {("2025-12-15", "2025-12-16")}
    ids, out = overdue_ids(data, "2025-12-17T07:30:00Z")  # 23:30 PST on 16 Dec
    assert "INV-0902" not in ids, out
    ids, out = overdue_ids(data, "2025-12-17T08:30:00Z")
    assert "INV-0902" in ids, out


def test_T2_plus_zero_offset_spelling_reads_the_same(data):
    assert due_shown(data, "INV-2008") == due_shown(data, "INV-2002")


def test_T2_commands_do_not_rewrite_data_files(data):
    kept = ("customers.json", "invoices.json", "payments.json")
    before = {name: (data / name).read_bytes() for name in kept}
    now = "2026-10-12T00:00:00Z"
    cli(data, now, "show", "INV-2002")
    cli(data, now, "show", "INV-0901")
    cli(data, now, "reminders")
    cli(data, now, "overdue")
    cli(data, now, "reminders", "--send")
    cli(data, now, "statement", "C002")
    cli(data, now, "list")
    assert {name: (data / name).read_bytes() for name in kept} == before
