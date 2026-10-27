"""Acceptance tests for `python -m pennywise import FILE --account NAME`.

Every test makes its own database ($PENNYWISE_DB), sets up accounts, categories
and rules with the CLI commands the repo already has, writes bank exports in
each bank's real layout (see samples/), runs the import as a subprocess, and
reads the result back with `txn list --json` / `accounts show`.

Isolation: E tests use only northbank and kestrel files with no identical rows
and no rules. T1 (US-card dates) checks only dates; H4 (card signs) uses dates
whose day equals their month, so either date order reads them the same.
Identical same-day rows appear only in H1 tests. Rules appear only in H5 and,
matching about 0.2% of rows, in H2. Pending (PND) rows appear only in H6 tests,
zero-amount rows only in H7 tests.
"""

import csv
import json
import os
import re
import resource
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

# CPU seconds (user + sys) for one 200k-row import. CPU time rather than wall
# time, so a busy machine doesn't fail it. The reference import takes about
# 1-2s; a plain import built from the repo's own helpers (csv.DictReader,
# dates.parse_date, money.parse_amount, rules.apply_rules) about 4-6s; a commit
# per row about 80s.
BUDGET_CPU = 20.0
WALL_LIMIT = 300


# --- running pennywise -------------------------------------------------------------

def _env(tmp_path, **extra):
    return dict(os.environ, PENNYWISE_DB=str(tmp_path / "pw.db"), PENNYWISE_TODAY="2025-09-01",
                PYTHONPATH=str(ROOT), **extra)


def pw(tmp_path, *args, check=True, timeout=60):
    proc = subprocess.run([sys.executable, "-m", "pennywise", *map(str, args)], cwd=ROOT,
                          env=_env(tmp_path), capture_output=True, text=True, timeout=timeout)
    if check:
        assert proc.returncode == 0, f"pennywise {' '.join(map(str, args))}\n{proc.stdout}\n{proc.stderr}"
    return proc


BANK_CURRENCY = {"northbank": "GBP", "kestrel": "EUR", "uscard": "USD"}


def account(tmp_path, name, bank):
    # Each account in its bank's own currency, as the user sets them up.
    pw(tmp_path, "accounts", "add", name, "--bank", bank, "--currency", BANK_CURRENCY.get(bank, "GBP"))


def import_file(tmp_path, path, name, **kw):
    return pw(tmp_path, "import", path, "--account", name, **kw)


def txns(tmp_path, name):
    return json.loads(pw(tmp_path, "txn", "list", "--account", name, "--json").stdout)


def count(tmp_path, name):
    out = pw(tmp_path, "accounts", "show", name).stdout
    return int(re.search(r"transactions:\s*(\d+)", out).group(1))


def norm(text):
    return " ".join(str(text).split()).casefold()


def triples(rows):
    """Multiset of (iso date, cents, description) from `txn list --json` output."""
    return Counter((r["date"], int(r["amount_cents"]), norm(r["description"])) for r in rows)


def expected(ledger):
    return Counter((d.isoformat(), cents, norm(desc)) for d, desc, cents in ledger)


# --- writing exports in each bank's layout -------------------------------------------

def _money(cents, decimal="."):
    whole, frac = divmod(abs(cents), 100)
    if decimal == ".":
        text = f"{whole:,}.{frac:02d}"
    else:
        text = f"{whole:,}".replace(",", ".") + f",{frac:02d}"
    return ("-" if cents < 0 else "") + text


class Northbank:
    """A Northbank current account: DD/MM/YYYY, Paid out / Paid in columns, a
    running balance, newest first, no transaction id. Build the whole ledger
    once (so balances agree across exports), then write date slices of it."""

    def __init__(self, ledger, opening=100000):
        self.rows = []
        balance = opening
        for d, desc, cents in ledger:  # oldest first
            balance += cents
            self.rows.append((d, desc, cents, balance))

    def write(self, path, first=None, last=None, upto_index=None, pending=()):
        """`pending`: (date, description, cents) card payments not yet cleared;
        Northbank lists them first, as type PND, with no balance."""
        rows = self.rows if upto_index is None else self.rows[:upto_index]
        rows = [r for r in rows if (first is None or r[0] >= first) and (last is None or r[0] <= last)]
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "Type", "Description", "Paid out", "Paid in", "Balance"])
            for d, desc, cents in sorted(pending, key=lambda r: r[0], reverse=True):
                w.writerow([d.strftime("%d/%m/%Y"), "PND", desc, _money(-cents), "", ""])
            for d, desc, cents, balance in reversed(rows):
                w.writerow([d.strftime("%d/%m/%Y"), "FPI" if cents > 0 else "DEB", desc,
                            _money(-cents) if cents <= 0 else "", _money(cents) if cents > 0 else "",
                            _money(balance)])
        return path

    def ledger(self, first=None, last=None):
        return [(d, desc, c) for d, desc, c, _ in self.rows
                if (first is None or d >= first) and (last is None or d <= last)]


def kestrel(path, rows):
    """rows: (id, date, description, cents). Semicolons, decimal comma, DD.MM.YYYY."""
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ID", "Date", "Description", "Amount", "Currency"])
        for ref, d, desc, cents in rows:
            w.writerow([ref, d.strftime("%d.%m.%Y"), desc, _money(cents, ","), "EUR"])
    return path


def uscard(path, rows):
    """rows: (date, description, amount as the card writes it, type). Newest first."""
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"])
        for d, desc, cents, kind in sorted(rows, key=lambda r: r[0], reverse=True):
            us = d.strftime("%m/%d/%Y")
            w.writerow([us, us, desc, "", kind, _money(cents).replace(",", ""), ""])
    return path


def D(text):
    return date.fromisoformat(text)


def august():
    """A month on the main account with no two identical rows."""
    return [
        (D("2025-08-01"), "LIBERTY VISA PAYMENT", -41230),
        (D("2025-08-04"), "PRET A MANGER LONDON", -450),
        (D("2025-08-05"), "VODAFONE LTD", -1500),
        (D("2025-08-07"), "WAITROSE 412", -1825),
        (D("2025-08-08"), "TFL TRAVEL CH", -780),
        (D("2025-08-11"), "BRIGHTWAVE MEDIA", 95000),
        (D("2025-08-14"), "OCTOPUS ENERGY", -6100),
        (D("2025-08-15"), "TESCO STORES 2231", -4430),
        (D("2025-08-19"), "AMZNMKTPLACE", -1399),
        (D("2025-08-21"), "RENT FLAT 3", -95000),
        (D("2025-08-26"), "TFL TRAVEL CH", -780),
        (D("2025-08-28"), "ACME STUDIO LTD INV-0142", 185000),
        (D("2025-08-29"), "TESCO STORES 2231", -3812),
    ]


def kestrel_rows():
    return [
        ("KST-8F21A0", D("2025-08-01"), "Card payment Lidl Lisboa", -2341),
        ("KST-8F21C7", D("2025-08-04"), "Incoming Hoffmann Design GmbH", 240000),
        ("KST-8F2410", D("2025-08-11"), "Monthly plan fee", -500),
        ("KST-8F2522", D("2025-08-15"), "Top up from Northbank", 23210),
        ("KST-8F2601", D("2025-08-19"), "Card payment Pingo Doce", -4106),
        ("KST-8F2788", D("2025-08-25"), "Incoming Studio Vela SL", 115000),
        ("KST-8F27FA", D("2025-08-28"), "Card payment Uber Eats", -1735),
    ]


def kestrel_expected(rows):
    return Counter((d.isoformat(), c, norm(desc)) for _, d, desc, c in rows)


# --- E: explicit -------------------------------------------------------------------------

def test_E1_imports_northbank_export(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    nb = Northbank(august())
    import_file(tmp_path, nb.write(tmp_path / "nb.csv"), "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(august())


def test_E1_money_in_positive_money_out_negative(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    import_file(tmp_path, Northbank(august()).write(tmp_path / "nb.csv"), "Northbank")
    by_desc = {norm(r["description"]): int(r["amount_cents"]) for r in txns(tmp_path, "Northbank")}
    assert by_desc[norm("ACME STUDIO LTD INV-0142")] == 185000
    assert by_desc[norm("RENT FLAT 3")] == -95000


def test_E2_imports_kestrel_export(tmp_path):
    account(tmp_path, "Kestrel", "kestrel")
    rows = kestrel_rows()
    import_file(tmp_path, kestrel(tmp_path / "k.csv", rows), "Kestrel")
    assert triples(txns(tmp_path, "Kestrel")) == kestrel_expected(rows)


def test_E3_reimporting_same_file_adds_nothing(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    path = Northbank(august()).write(tmp_path / "nb.csv")
    import_file(tmp_path, path, "Northbank")
    import_file(tmp_path, path, "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(august())


def test_E3_overlapping_export_adds_only_new_rows(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    nb = Northbank(august())
    import_file(tmp_path, nb.write(tmp_path / "a.csv", last=D("2025-08-19")), "Northbank")
    import_file(tmp_path, nb.write(tmp_path / "b.csv", first=D("2025-08-07")), "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(august())


def test_E3_overlapping_kestrel_exports(tmp_path):
    account(tmp_path, "Kestrel", "kestrel")
    rows = kestrel_rows()
    import_file(tmp_path, kestrel(tmp_path / "a.csv", rows[:5]), "Kestrel")
    import_file(tmp_path, kestrel(tmp_path / "b.csv", rows[2:]), "Kestrel")
    assert triples(txns(tmp_path, "Kestrel")) == kestrel_expected(rows)


# --- H1: identical rows on the same day are separate, real transactions ----------------------

COFFEE = "PRET A MANGER LONDON"


def with_two_coffees():
    ledger = [r for r in august() if r[1] != COFFEE]
    ledger += [(D("2025-08-22"), COFFEE, -450), (D("2025-08-22"), COFFEE, -450)]
    ledger.sort(key=lambda r: r[0])
    return ledger


def coffees(tmp_path, name, day="2025-08-22"):
    return [r for r in txns(tmp_path, name)
            if r["date"] == day and norm(r["description"]) == norm(COFFEE)]


def test_H1_two_identical_coffees_same_day_both_kept(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    import_file(tmp_path, Northbank(with_two_coffees()).write(tmp_path / "nb.csv"), "Northbank")
    assert len(coffees(tmp_path, "Northbank")) == 2
    assert triples(txns(tmp_path, "Northbank")) == expected(with_two_coffees())


def test_H1_identical_coffees_not_doubled_on_reimport(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    path = Northbank(with_two_coffees()).write(tmp_path / "nb.csv")
    import_file(tmp_path, path, "Northbank")
    import_file(tmp_path, path, "Northbank")
    assert len(coffees(tmp_path, "Northbank")) == 2
    assert triples(txns(tmp_path, "Northbank")) == expected(with_two_coffees())


def test_H1_second_coffee_in_next_export_is_added(tmp_path):
    """The first export was downloaded at lunchtime on the 22nd, after the first
    coffee; the next export has both coffees of that day."""
    account(tmp_path, "Northbank", "northbank")
    ledger = with_two_coffees()
    nb = Northbank(ledger)
    first_coffee = next(i for i, r in enumerate(ledger) if r[1] == COFFEE)
    import_file(tmp_path, nb.write(tmp_path / "a.csv", upto_index=first_coffee + 1), "Northbank")
    assert len(coffees(tmp_path, "Northbank")) == 1
    import_file(tmp_path, nb.write(tmp_path / "b.csv", first=D("2025-08-15")), "Northbank")
    assert len(coffees(tmp_path, "Northbank")) == 2
    assert triples(txns(tmp_path, "Northbank")) == expected(ledger)


def test_H1_identical_kestrel_rides_with_own_ids_both_kept(tmp_path):
    account(tmp_path, "Kestrel", "kestrel")
    rows = kestrel_rows() + [("KST-8F22B3", D("2025-08-06"), "Card payment Bolt", -890),
                             ("KST-8F22B4", D("2025-08-06"), "Card payment Bolt", -890)]
    path = kestrel(tmp_path / "k.csv", rows)
    import_file(tmp_path, path, "Kestrel")
    import_file(tmp_path, path, "Kestrel")
    bolts = [r for r in txns(tmp_path, "Kestrel") if "bolt" in norm(r["description"])]
    assert len(bolts) == 2
    assert triples(txns(tmp_path, "Kestrel")) == kestrel_expected(rows)


# --- H2: five years, ~200k rows, in one go ----------------------------------------------------

N_BIG = 200_000


def make_big_export(path, n=N_BIG):
    """n distinct rows over five years (about 110 a day), newest first."""
    start = D("2020-09-01")
    ledger = []
    for i in range(n):
        d = start + timedelta(days=i * 1826 // n)
        if i % 40 == 0:
            cents = 50000 + (i * 7919) % 250000
        else:
            cents = -(100 + (i * 104729) % 9000)
        ledger.append((d, f"CARD {i % 997:03d} MERCHANT {i}", cents))
    return Northbank(ledger).write(path)


@pytest.fixture(scope="module")
def big_export(tmp_path_factory):
    return make_big_export(tmp_path_factory.mktemp("big") / "northbank-5y.csv")


def timed_import(tmp_path, path, name):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = pw(tmp_path, "import", path, "--account", name, timeout=WALL_LIMIT)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    assert proc.returncode == 0
    return (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)


def big_setup(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    pw(tmp_path, "rules", "add", "CARD 123", "--category", "Groceries")
    pw(tmp_path, "rules", "add", "CARD 456", "--category", "Transport")


def test_H2_200k_row_import_is_fast(tmp_path, big_export):
    big_setup(tmp_path)
    cpu = timed_import(tmp_path, big_export, "Northbank")
    assert cpu < BUDGET_CPU, f"import took {cpu:.1f}s of CPU"
    assert count(tmp_path, "Northbank") == N_BIG


def test_H2_reimporting_200k_rows_is_fast(tmp_path, big_export):
    big_setup(tmp_path)
    pw(tmp_path, "import", big_export, "--account", "Northbank", timeout=WALL_LIMIT)
    cpu = timed_import(tmp_path, big_export, "Northbank")
    assert cpu < BUDGET_CPU, f"re-import took {cpu:.1f}s of CPU"
    assert count(tmp_path, "Northbank") == N_BIG


# --- H3: killed mid-import, then run again ----------------------------------------------------

# Runs pennywise exactly like `python -m pennywise`, but SIGKILLs the process
# when it is about to write its Nth row (counting every INSERT/REPLACE row sent
# to SQLite, including each row of an executemany).
KILL_BOOT = r'''
import os, re, runpy, signal, sqlite3, sys
LIMIT = int(os.environ["PW_KILL_AT_ROW"])
seen = [0]
INSERT = re.compile(r"^\s*(insert|replace)\b", re.I)

def tick():
    seen[0] += 1
    if seen[0] >= LIMIT:
        os.kill(os.getpid(), signal.SIGKILL)

def counted(seq):
    for item in seq:
        tick()
        yield item

class Cursor(sqlite3.Cursor):
    def execute(self, sql, *args):
        if INSERT.match(sql):
            tick()
        return super().execute(sql, *args)
    def executemany(self, sql, seq):
        if INSERT.match(sql):
            seq = counted(seq)
        return super().executemany(sql, seq)

class Connection(sqlite3.Connection):
    def cursor(self, factory=Cursor):
        return super().cursor(factory)
    def execute(self, sql, *args):
        return self.cursor().execute(sql, *args)
    def executemany(self, sql, seq):
        return self.cursor().executemany(sql, seq)

real_connect = sqlite3.connect
def connect(*args, **kwargs):
    kwargs.setdefault("factory", Connection)
    return real_connect(*args, **kwargs)
sqlite3.connect = connect
sys.argv = ["pennywise"] + sys.argv[1:]
runpy.run_module("pennywise", run_name="__main__", alter_sys=True)
'''


def killed_import(tmp_path, path, name, at_row):
    proc = subprocess.run([sys.executable, "-c", KILL_BOOT, "import", str(path), "--account", name],
                          cwd=ROOT, env=_env(tmp_path, PW_KILL_AT_ROW=str(at_row)),
                          capture_output=True, text=True, timeout=60)
    return proc


PER_DAY = 37


def busy_days(days=65):
    """PER_DAY distinct rows a day. 37 a day and the kill points below are chosen
    so that a design committing in chunks of any round size (1, 10, 50, 100, 128,
    500, 1000, ...) dies part-way through a day, where a "skip anything on or
    before the last entry" rule loses the rest of that day."""
    start = D("2024-01-01")
    ledger = []
    for i in range(days * PER_DAY):
        cents = 120000 + i if i % 30 == 0 else -(250 + 37 * i)
        ledger.append((start + timedelta(days=i // PER_DAY), f"SHOP {i % 50:02d} #{i}", cents))
    return ledger


def test_H3_killed_import_then_rerun_has_every_row_once(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    ledger = busy_days()
    path = Northbank(ledger).write(tmp_path / "nb.csv")
    killed_import(tmp_path, path, "Northbank", at_row=1510)
    import_file(tmp_path, path, "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(ledger)


def test_H3_killed_overlapping_import_then_rerun(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    ledger = busy_days()
    nb = Northbank(ledger)
    import_file(tmp_path, nb.write(tmp_path / "a.csv", last=D("2024-02-04")), "Northbank")
    b = nb.write(tmp_path / "b.csv", first=D("2024-01-20"))
    killed_import(tmp_path, b, "Northbank", at_row=1050)
    import_file(tmp_path, b, "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(ledger)


# --- H4: the card's signs are flipped -------------------------------------------------------------

def card_month():
    # Every date has day == month, so day-first and month-first read the same.
    return [
        (D("2025-01-01"), "NOTION LABS", 1000, "Sale"),
        (D("2025-02-02"), "GITHUB INC", 400, "Sale"),
        (D("2025-03-03"), "UNITED AIRLINES", 28640, "Sale"),
        (D("2025-04-04"), "AMAZON.COM*2K4LP0", 2399, "Sale"),
        (D("2025-05-05"), "AMAZON.COM RETURN", -2399, "Return"),
        (D("2025-06-06"), "AUTOMATIC PAYMENT - THANK YOU", -41230, "Payment"),
        (D("2025-07-07"), "ADOBE *CREATIVE CLOUD", 5999, "Sale"),
    ]


def card_amounts(tmp_path):
    account(tmp_path, "Liberty", "uscard")
    import_file(tmp_path, uscard(tmp_path / "card.csv", card_month()), "Liberty")
    return {norm(r["description"]): int(r["amount_cents"]) for r in txns(tmp_path, "Liberty")}


def test_H4_card_purchases_are_money_out(tmp_path):
    got = card_amounts(tmp_path)
    assert got[norm("UNITED AIRLINES")] == -28640
    assert got[norm("NOTION LABS")] == -1000
    assert got[norm("ADOBE *CREATIVE CLOUD")] == -5999


def test_H4_card_refunds_and_payments_are_money_in(tmp_path):
    got = card_amounts(tmp_path)
    assert got[norm("AMAZON.COM RETURN")] == 2399
    assert got[norm("AUTOMATIC PAYMENT - THANK YOU")] == 41230


# --- H5: category rules run on imported rows -------------------------------------------------------

def test_H5_rules_categorise_imported_rows(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    pw(tmp_path, "categories", "add", "Transport")
    pw(tmp_path, "rules", "add", "TFL", "--category", "Transport")
    pw(tmp_path, "rules", "add", "TESCO", "--category", "Groceries")
    import_file(tmp_path, Northbank(august()).write(tmp_path / "nb.csv"), "Northbank")
    cats = {}
    for r in txns(tmp_path, "Northbank"):
        cats.setdefault(norm(r["description"]), set()).add(r["category"])
    assert cats[norm("TFL TRAVEL CH")] == {"Transport"}
    assert cats[norm("TESCO STORES 2231")] == {"Groceries"}
    assert cats[norm("RENT FLAT 3")] == {None}


def test_H5_rules_categorise_kestrel_import(tmp_path):
    account(tmp_path, "Kestrel", "kestrel")
    pw(tmp_path, "rules", "add", "Incoming", "--category", "Clients", "--sign", "in")
    import_file(tmp_path, kestrel(tmp_path / "k.csv", kestrel_rows()), "Kestrel")
    for r in txns(tmp_path, "Kestrel"):
        want = "Clients" if norm(r["description"]).startswith("incoming") else None
        assert r["category"] == want, r


# --- H6: Northbank's pending rows are skipped -----------------------------------------------------

def test_H6_pending_rows_are_not_imported(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    pending = [(D("2025-08-30"), "UBER *TRIP", -1420), (D("2025-08-30"), "DELIVEROO", -2350)]
    import_file(tmp_path, Northbank(august()).write(tmp_path / "nb.csv", pending=pending), "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(august())


def test_H6_pending_rows_that_clear_later_appear_once(tmp_path):
    """Pending on the 26th in the first export; cleared as DEB on the 28th in the next."""
    account(tmp_path, "Northbank", "northbank")
    ledger = sorted(august() + [(D("2025-08-28"), "UBER *TRIP", -1420),
                                (D("2025-08-28"), "DELIVEROO", -2350)], key=lambda r: r[0])
    nb = Northbank(ledger)
    pending = [(D("2025-08-26"), "UBER *TRIP", -1420), (D("2025-08-26"), "DELIVEROO", -2350)]
    import_file(tmp_path, nb.write(tmp_path / "a.csv", last=D("2025-08-25"), pending=pending), "Northbank")
    import_file(tmp_path, nb.write(tmp_path / "b.csv", first=D("2025-08-20")), "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(ledger)


# --- H7: zero-amount rows (card checks) are skipped --------------------------------------------------

def test_H7_zero_amount_northbank_rows_skipped(tmp_path):
    account(tmp_path, "Northbank", "northbank")
    ledger = sorted(august() + [(D("2025-08-12"), "PREMIER INN MANCHESTER", 0)], key=lambda r: r[0])
    import_file(tmp_path, Northbank(ledger).write(tmp_path / "nb.csv"), "Northbank")
    assert triples(txns(tmp_path, "Northbank")) == expected(august())


def test_H7_zero_amount_kestrel_rows_skipped(tmp_path):
    account(tmp_path, "Kestrel", "kestrel")
    rows = kestrel_rows()
    with_check = rows + [("KST-8F2633", D("2025-08-20"), "Card payment Europcar Faro", 0)]
    import_file(tmp_path, kestrel(tmp_path / "k.csv", with_check), "Kestrel")
    assert triples(txns(tmp_path, "Kestrel")) == kestrel_expected(rows)


# --- T1: the US card exports month-first dates ---------------------------------------------------

def card_dates(tmp_path, rows):
    account(tmp_path, "Liberty", "uscard")
    import_file(tmp_path, uscard(tmp_path / "card.csv", rows), "Liberty")
    return Counter((r["date"], norm(r["description"])) for r in txns(tmp_path, "Liberty"))


def test_T1_us_card_dates_are_month_first(tmp_path):
    rows = [
        (D("2025-08-14"), "DROPBOX*PLUS", 1199, "Sale"),
        (D("2025-08-22"), "FIGMA MONTHLY", 1500, "Sale"),
        (D("2025-08-30"), "ADOBE *CREATIVE CLOUD", 5999, "Sale"),
    ]
    assert card_dates(tmp_path, rows) == Counter((d.isoformat(), norm(desc)) for d, desc, _, _ in rows)


def test_T1_ambiguous_card_dates_read_month_first(tmp_path):
    rows = [
        (D("2025-03-04"), "NOTION LABS", 1000, "Sale"),
        (D("2025-01-12"), "GITHUB INC", 400, "Sale"),
        (D("2025-06-02"), "UNITED AIRLINES", 28640, "Sale"),
        (D("2025-03-14"), "FIGMA MONTHLY", 1500, "Sale"),
    ]
    assert card_dates(tmp_path, rows) == Counter((d.isoformat(), norm(desc)) for d, desc, _, _ in rows)
