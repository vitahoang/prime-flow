"""Acceptance tests for meterly.invoicing.build_invoice(customer_id, period_start, period_end).

Each test writes its own data directory in the repo's file formats, points
METERLY_DATA at it, and calls build_invoice in a fresh subprocess (so an
implementation that caches the store per process is fine). The subprocess
prints the invoice's lines (description, amount_cents) and total_cents.

Isolation: every scenario is neutral on every rule but the one its id owns.
Unless a test says otherwise the customer is in GB (20% VAT in both tax.py and
config.VAT_RATE), pays in GBP, has no credit, one plan with a single
open-ended tier, no free units and no minimum; all events carry units=1, have
unique ids, sit mid-period and arrive a minute after they happen; and every
line comes to whole pence before tax, so rounding order can't matter.
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SEP = (date(2026, 9, 1), date(2026, 10, 1))
OCT = (date(2026, 10, 1), date(2026, 11, 1))
FEB = (date(2027, 2, 1), date(2027, 3, 1))
LONG_AGO = "2025-01-01T00:00:00Z"
CID = "cus_test"


def ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Scenario:
    def __init__(self, country="GB", currency="GBP", tz="Europe/London", credit="0", tags=()):
        self.customer = {"id": CID, "name": "Test Co", "email": "t@test.example", "country": country,
                         "currency": currency, "timezone": tz, "plan_id": None,
                         "credit_balance": credit, "created_at": LONG_AGO, "tags": list(tags)}
        self.currency = currency
        self.plans, self.subs, self.events = [], [], []
        self._n = 0

    def plan(self, pid, base, tiers=((None, "1.00"),), free=0, minimum="0"):
        self.plans.append({"id": pid, "name": pid.title(), "currency": self.currency, "base_fee": base,
                           "free_units": free, "minimum_charge": minimum,
                           "tiers": [{"up_to": u, "unit_price": p} for u, p in tiers]})
        return self

    def on(self, pid, at=LONG_AGO):
        """Start ``pid`` at ``at``, the way subscriptions.change_plan writes it."""
        self.subs.append({"customer_id": CID, "plan_id": pid, "started_at": at})
        self.customer["plan_id"] = pid
        return self

    def event(self, when, units=1, event_id=None, received=None, metric="api_calls"):
        self._n += 1
        received = received or when + timedelta(minutes=1)
        self.events.append({"event_id": event_id or f"evt_{self._n:06d}", "customer_id": CID,
                            "timestamp": ts(when), "received_at": ts(received), "units": units,
                            "metric": metric, "source": "sdk" if units == 1 else "batch"})
        return self

    def calls(self, n, day=date(2026, 9, 10), metric="api_calls"):
        start = datetime(day.year, day.month, day.day, 10 if metric == "api_calls" else 14, 0, tzinfo=timezone.utc)
        for i in range(n):
            self.event(start + timedelta(minutes=i), metric=metric)
        return self

    def write(self, root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "customers.json").write_text(json.dumps([self.customer]))
        (root / "plans.json").write_text(json.dumps(self.plans))
        (root / "subscriptions.json").write_text(json.dumps(self.subs))
        rows = sorted(self.events, key=lambda e: e["received_at"])
        (root / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in rows))
        return root


SCRIPT = r"""
import json, sys
from datetime import date
from meterly.invoicing import build_invoice
inv = build_invoice(sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
val = lambda obj, name: (lambda v: v() if callable(v) else v)(getattr(obj, name))  # attribute, property or method
lines = val(inv, "lines")
print("@@INVOICE@@" + json.dumps({
    "lines": [{"description": str(val(l, "description")), "amount_cents": str(val(l, "amount_cents"))} for l in lines],
    "total_cents": str(val(inv, "total_cents")),
}))
"""


def invoice(tmp_path, sc, period=SEP):
    data = sc.write(tmp_path / "data")
    env = dict(os.environ, METERLY_DATA=str(data), PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-c", SCRIPT, CID, period[0].isoformat(), period[1].isoformat()],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    payload = proc.stdout.split("@@INVOICE@@")[-1]
    out = json.loads(payload)
    for line in out["lines"]:
        line["amount_cents"] = Decimal(line["amount_cents"])
    out["total_cents"] = Decimal(out["total_cents"])
    return out


def amounts(inv):
    return [l["amount_cents"] for l in inv["lines"]]


def gb(base="10.00", **plan_kw):
    return Scenario().plan("main", base, **plan_kw).on("main")


# --- explicit -------------------------------------------------------------------

def test_E1_total_is_base_plus_usage_plus_vat(tmp_path):
    sc = gb("49.00", tiers=((None, "0.25"),)).calls(4)
    # 49.00 + 4 x 0.25 = 50.00, + 20% VAT = 60.00
    assert invoice(tmp_path, sc)["total_cents"] == 6000


def test_E2_lines_have_description_and_amount_cents(tmp_path):
    sc = gb("49.00", tiers=((None, "0.25"),)).calls(4)
    inv = invoice(tmp_path, sc)
    assert inv["lines"]
    for line in inv["lines"]:
        assert line["description"].strip()
        assert line["amount_cents"] == line["amount_cents"].to_integral_value()
    assert 4900 in amounts(inv)


# --- T1: usage is the sum of units, not a count of events -------------------------

def test_T1_batch_event_units_are_summed(tmp_path):
    sc = gb("10.00", tiers=((None, "0.10"),)).calls(3)
    sc.event(datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc), units=100)
    # 103 units x 0.10 = 10.30; 20.30 + VAT 4.06 = 24.36 (counting events: 12.48)
    assert invoice(tmp_path, sc)["total_cents"] == 2436


def test_T1_batches_only(tmp_path):
    sc = gb("0", tiers=((None, "0.02"),))
    sc.event(datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc), units=250)
    sc.event(datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc), units=150)
    # 400 x 0.02 = 8.00 + VAT = 9.60
    assert invoice(tmp_path, sc)["total_cents"] == 960


# --- T2: graduated tiers ------------------------------------------------------------

TIERS = ((10, "1.00"), (100, "0.50"), (None, "0.20"))


def test_T2_graduated_two_tiers(tmp_path):
    sc = gb("0", tiers=TIERS).calls(50)
    # 10 x 1.00 + 40 x 0.50 = 30.00 + VAT = 36.00 (volume: 25.00 -> 30.00)
    assert invoice(tmp_path, sc)["total_cents"] == 3600


def test_T2_graduated_three_tiers(tmp_path):
    sc = gb("0", tiers=TIERS).calls(200)
    # 10 + 90 x 0.50 + 100 x 0.20 = 75.00 + VAT = 90.00 (volume: 40.00 -> 48.00)
    assert invoice(tmp_path, sc)["total_cents"] == 9000


# --- H1: free units -------------------------------------------------------------------

def test_H1_free_units_come_off_usage(tmp_path):
    sc = gb("20.00", free=10).calls(15)
    # 5 billable x 1.00 + 20.00 = 25.00 + VAT = 30.00
    assert invoice(tmp_path, sc)["total_cents"] == 3000


def test_H1_usage_under_free_allowance_is_free(tmp_path):
    sc = gb("20.00", free=10).calls(8)
    assert invoice(tmp_path, sc)["total_cents"] == 2400


# --- H2: dedupe by event_id -------------------------------------------------------------

def test_H2_retried_event_counted_once(tmp_path):
    sc = gb("10.00").calls(5)
    first = sc.events[2]
    when = datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
    for secs in (5, 30):
        sc.event(when, event_id=first["event_id"], received=when + timedelta(minutes=1, seconds=secs))
    # 5 calls -> 15.00 + VAT = 18.00 (no dedupe: 7 calls -> 20.40)
    assert invoice(tmp_path, sc)["total_cents"] == 1800


def test_H2_every_event_sent_twice(tmp_path):
    sc = gb("10.00").calls(3)
    for e in list(sc.events):
        when = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        sc.event(when, event_id=e["event_id"], received=when + timedelta(minutes=2))
    assert invoice(tmp_path, sc)["total_cents"] == 1560


# --- H3: late events within 3 days -------------------------------------------------------

def test_H3_event_arriving_two_days_late_is_billed(tmp_path):
    sc = gb("10.00").calls(4)
    sc.event(datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
             received=datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc))
    # 5 calls -> 15.00 + VAT = 18.00
    assert invoice(tmp_path, sc)["total_cents"] == 1800


def test_H3_event_arriving_a_week_late_is_dropped(tmp_path):
    sc = gb("10.00").calls(4)
    sc.event(datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
             received=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc))
    # only the 4 on-time calls -> 14.00 + VAT = 16.80
    assert invoice(tmp_path, sc)["total_cents"] == 1680


# --- H4: minimum charge ---------------------------------------------------------------------

def test_H4_topped_up_to_minimum_before_tax(tmp_path):
    sc = gb("10.00", minimum="25.00").calls(2)
    # 12.00 -> minimum 25.00, + VAT = 30.00
    assert invoice(tmp_path, sc)["total_cents"] == 3000


def test_H4_usage_only_plan_minimum(tmp_path):
    sc = gb("0", minimum="20.00").calls(3)
    assert invoice(tmp_path, sc)["total_cents"] == 2400


# --- H5: currency minor units (JPY has none) --------------------------------------------------

def jp(price, n):
    sc = Scenario(country="JP", currency="JPY", tz="Asia/Tokyo").plan("jp", "3000", tiers=((None, price),)).on("jp")
    return sc.calls(n)


def test_H5_jpy_amounts_are_whole_yen(tmp_path):
    inv = invoice(tmp_path, jp("1.5", 120))
    assert 3000 in amounts(inv) and 180 in amounts(inv)
    assert 3180 <= inv["total_cents"] <= 3180 * Decimal("1.25")


def test_H5_jpy_rounds_to_the_yen(tmp_path):
    inv = invoice(tmp_path, jp("1.3", 101))  # 131.3 yen of usage
    assert 131 in amounts(inv)
    assert all(a == a.to_integral_value() for a in amounts(inv))
    assert 3131 <= inv["total_cents"] <= 3131 * Decimal("1.25")


# --- H6: tax by customer country ---------------------------------------------------------------

def test_H6_german_customer_pays_19_percent(tmp_path):
    sc = Scenario(country="DE", currency="EUR", tz="Europe/Berlin").plan("eu", "100.00").on("eu")
    assert invoice(tmp_path, sc)["total_cents"] == 11900


def test_H6_no_tax_where_not_registered(tmp_path):
    sc = Scenario(country="US", currency="USD", tz="America/New_York").plan("us", "100.00").on("us")
    assert invoice(tmp_path, sc)["total_cents"] == 10000


# --- H7: credit balance, last, never below zero --------------------------------------------------

def test_H7_credit_applied_after_tax(tmp_path):
    sc = Scenario(credit="10.00").plan("main", "50.00").on("main")
    # 50.00 + VAT 10.00 = 60.00 - 10.00 credit = 50.00 (credit before tax: 48.00)
    assert invoice(tmp_path, sc)["total_cents"] == 5000


def test_H7_credit_never_takes_total_below_zero(tmp_path):
    sc = Scenario(credit="500.00").plan("main", "50.00").on("main")
    assert invoice(tmp_path, sc)["total_cents"] == 0


# --- H8: proration on a plan change -----------------------------------------------------------------

def change(tz, old, new, at):
    sc = Scenario(tz=tz).plan("old", old).plan("new", new)
    return sc.on("old").on("new", at=at)


def test_H8_february_change_day_on_new_plan(tmp_path):
    sc = change("Europe/London", "28.00", "56.00", "2027-02-15T10:00:00Z")
    # Feb 1-14 on old (14/28), Feb 15-28 on new (14/28): 14.00 + 28.00 = 42.00 + VAT = 50.40
    assert invoice(tmp_path, sc, FEB)["total_cents"] == 5040


def test_H8_change_day_is_the_customers_local_day(tmp_path):
    sc = change("America/New_York", "30.00", "90.00", "2026-09-11T02:00:00Z")  # 10 Sep, 22:00 in New York
    # Sep 1-9 old (9/30), Sep 10-30 new (21/30): 9.00 + 63.00 = 72.00 + VAT = 86.40
    assert invoice(tmp_path, sc, SEP)["total_cents"] == 8640


def test_H8_thirty_one_day_month(tmp_path):
    sc = change("Europe/London", "31.00", "62.00", "2026-10-11T12:00:00Z")
    # Oct 1-10 old (10/31), Oct 11-31 new (21/31): 10.00 + 42.00 = 52.00 + VAT = 62.40
    assert invoice(tmp_path, sc, OCT)["total_cents"] == 6240


# --- H9: round each line, then sum ---------------------------------------------------------------------

def test_H9_total_is_sum_of_rounded_lines(tmp_path):
    sc = gb("50.00", tiers=((None, "1.2015"),)).calls(3)
    # usage 3.6045 -> 3.60; 53.60 + VAT 10.72 = 64.32 (rounding once at the end: 64.33)
    inv = invoice(tmp_path, sc)
    assert inv["total_cents"] == 6432
    assert inv["total_cents"] == sum(amounts(inv))


def test_H9_line_rounding_up(tmp_path):
    sc = gb("20.00", tiers=((None, "0.6671"),)).calls(5)
    # usage 3.3355 -> 3.34; 23.34 + VAT 4.67 = 28.01 (rounding once at the end: 28.00)
    inv = invoice(tmp_path, sc)
    assert inv["total_cents"] == 2801
    assert inv["total_cents"] == sum(amounts(inv))


# --- H10: charities pay half the base fee (unhinted) -----------------------------------------------

def test_H10_charity_pays_half_base_fee_full_usage(tmp_path):
    sc = Scenario(tags=["charity"]).plan("main", "50.00").on("main").calls(4)
    # 25.00 + 4 x 1.00 = 29.00 + VAT = 34.80 (half of everything: 32.40; no discount: 64.80)
    assert invoice(tmp_path, sc)["total_cents"] == 3480


def test_H10_charity_base_only(tmp_path):
    sc = Scenario(tags=["priority-support", "charity"]).plan("main", "30.00").on("main")
    assert invoice(tmp_path, sc)["total_cents"] == 1800


# --- H11: sandbox calls are never billed (unhinted) --------------------------------------------------

def test_H11_sandbox_calls_not_billed(tmp_path):
    sc = gb("10.00").calls(4).calls(6, metric="sandbox_calls")
    # 4 real calls -> 14.00 + VAT = 16.80
    assert invoice(tmp_path, sc)["total_cents"] == 1680


def test_H11_sandbox_only_month(tmp_path):
    sc = gb("10.00").calls(5, metric="sandbox_calls")
    assert invoice(tmp_path, sc)["total_cents"] == 1200


# --- H12: pilot deals pay no usage on their first two invoices (unhinted) ---------------------------

def pilot(signed_up):
    sc = Scenario(tags=["pilot"]).plan("main", "10.00")
    sc.customer["created_at"] = signed_up
    return sc.on("main", at=signed_up).calls(5)


def test_H12_pilot_second_invoice_has_no_usage(tmp_path):
    sc = pilot("2026-08-03T09:00:00Z")  # September is their 2nd invoice
    # base 10.00 only + VAT = 12.00 (with usage: 18.00)
    assert invoice(tmp_path, sc)["total_cents"] == 1200


def test_H12_pilot_first_invoice_has_no_usage(tmp_path):
    sc = pilot("2026-08-31T23:00:00Z")  # 1 Sep, 00:00 in London: September is their 1st invoice
    assert invoice(tmp_path, sc)["total_cents"] == 1200


def test_H12_pilot_third_invoice_pays_usage(tmp_path):
    sc = pilot("2026-07-14T09:00:00Z")  # September is their 3rd invoice
    assert invoice(tmp_path, sc)["total_cents"] == 1800


# --- H13: Irish customers are reverse-charged (unhinted) ---------------------------------------------

def ie(base="100.00"):
    return Scenario(country="IE", currency="EUR", tz="Europe/Dublin").plan("eu", base).on("eu")


def test_H13_ireland_no_tax(tmp_path):
    # tax.py lists IE at 23%; reverse charge means none is added
    assert invoice(tmp_path, ie().calls(5))["total_cents"] == 10500


def test_H13_ireland_reverse_charge_line(tmp_path):
    inv = invoice(tmp_path, ie())
    rc = [l for l in inv["lines"] if "reverse charge" in l["description"].lower()]
    assert rc and all(l["amount_cents"] == 0 for l in rc)
    assert inv["total_cents"] == 10000
