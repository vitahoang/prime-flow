"""Acceptance tests for `python -m stockroom reorder [--shop SHOP] [--json]`.

Every test writes its own data directory (the repo's own file formats), points
STOCKROOM_DATA at it, and runs the command as a subprocess. Dates are relative
to today; STOCKROOM_TODAY is set to the same date.

Daily sales in most scenarios run on today and each of the 60 days before, so
any reasonable "last 28 days" window (with or without today) gives nearly the
same rate. Quantity checks allow for that.

Isolation: each id's tests depend only on that id's rule. Scenarios for other
ids sit far from the boundary, so they give the same result for any safety
cushion from 0 to 5 days and any order cover from 7 to 21 days. H1 owns the
3-day cushion and the 28-day window; H4 owns the lead + 14 cap.
"""

import csv
import json
import math
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TODAY = date.today()

SHOPS = [
    {"code": "HAR", "name": "Harbour"},
    {"code": "MKT", "name": "Market Street"},
    {"code": "STN", "name": "Station Road"},
]
SHOP_NAMES = {s["code"]: s["name"] for s in SHOPS}
FIELDS = ["date", "shop", "sku", "type", "qty", "ref", "note"]
LO, HI = 27 / 28, 29 / 28  # tolerance on a measured daily rate


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


class Scenario:
    def __init__(self):
        self.items, self.suppliers, self.moves, self.orders = [], {}, [], []
        self._po = 0

    def supplier(self, sid, lead):
        self.suppliers[sid] = {"id": sid, "name": sid.title(), "lead_time_days": lead, "items": []}
        return self

    def item(self, sku, supplier, case=1, min_stock=0):
        self.items.append({"sku": sku, "name": sku.title(), "unit": "each", "supplier": supplier,
                           "category": "other", "min_stock": min_stock})
        self.suppliers[supplier]["items"].append({"sku": sku, "case_size": case, "unit_cost": 1.0})
        return self

    def move(self, offset, shop, sku, mtype, qty, ref=""):
        self.moves.append([day(offset), shop, sku, mtype, qty, ref, ""])

    def daily(self, shop, sku, mtype, per_day, first=-60, last=-1):
        for d in range(first, last + 1):
            self.move(d, shop, sku, mtype, per_day)

    def stock(self, shop, sku, on_hand, out_later):
        """Opening delivery 70 days ago so that, after `out_later` units leave,
        `on_hand` remain."""
        self.move(-70, shop, sku, "delivery", on_hand + out_later, "opening")

    def steady(self, shop, sku, per_day, on_hand):
        """`per_day` sold on each of the 60 days before today and today, ending
        with `on_hand`. Any N-day window ending today or yesterday sees N/N."""
        self.stock(shop, sku, on_hand, per_day * 61)
        self.daily(shop, sku, "sale", per_day, last=0)

    def po(self, shop, sku, qty, status="open", supplier=None):
        self._po += 1
        sup = supplier or next(i["supplier"] for i in self.items if i["sku"] == sku)
        self.orders.append({"id": f"PO-{self._po:04d}", "supplier": sup, "shop": shop,
                            "status": status, "ordered": day(-1), "expected": day(2),
                            "lines": [{"sku": sku, "qty": qty}]})

    def write(self, root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "shops.json").write_text(json.dumps(SHOPS))
        (root / "items.json").write_text(json.dumps(self.items))
        (root / "suppliers.json").write_text(json.dumps(list(self.suppliers.values())))
        (root / "purchase_orders.json").write_text(json.dumps(self.orders))
        rows = sorted(self.moves, key=lambda r: r[0])
        with (root / "movements.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FIELDS)
            w.writerows(rows)
        return root


def run(tmp_path, sc, *args):
    data = sc.write(tmp_path / "data")
    env = dict(os.environ, STOCKROOM_DATA=str(data), STOCKROOM_TODAY=TODAY.isoformat(),
               PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-m", "stockroom", "reorder", *args],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _parse(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        assert starts, f"no JSON in output: {text[:300]}"
        return json.loads(text[min(starts):])


def rows_json(tmp_path, sc, *args):
    data = _parse(run(tmp_path, sc, "--json", *args))
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        assert lists, f"no list in JSON output: {data}"
        data = lists[0]
    assert isinstance(data, list)
    for r in data:
        assert {"sku", "shop", "order_qty"} <= set(r), r
    return [r for r in data if float(r["order_qty"] or 0) > 0]


def _shop_is(row, code):
    value = str(row["shop"]).strip().lower()
    return value in (code.lower(), SHOP_NAMES[code].lower())


def find(rows, sku, shop="MKT"):
    found = [r for r in rows if str(r["sku"]).upper() == sku and _shop_is(r, shop)]
    return float(found[0]["order_qty"]) if found else None


def target_range(per_day, lead, cover, case=1):
    """Acceptable order_qty: (lead + 14) days of usage minus cover, rounded up to a case."""
    lo = per_day * LO * (lead + 14) - cover
    hi = per_day * HI * (lead + 14) - cover
    return math.ceil(lo / case) * case - 0.01, math.ceil(hi / case) * case + 0.01


# --- explicit -------------------------------------------------------------------

def _basic():
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy", min_stock=20).item("CUPS", "dairy", min_stock=10)
    sc.steady("MKT", "OAT", 10, 0)
    sc.steady("MKT", "CUPS", 1, 500)
    return sc


def test_E1_text_lists_item_that_is_out(tmp_path):
    out = run(tmp_path, _basic())
    assert "OAT" in out
    assert "CUPS" not in out


def test_E2_json_has_sku_shop_order_qty(tmp_path):
    rows = rows_json(tmp_path, _basic())
    oat = [r for r in rows if r["sku"] == "OAT"]
    assert oat and float(oat[0]["order_qty"]) > 0
    assert not [r for r in rows if r["sku"] == "CUPS"]


def test_E3_shop_filter(tmp_path):
    rows = rows_json(tmp_path, _basic(), "--shop", "MKT")
    assert rows
    assert all(_shop_is(r, "MKT") for r in rows)
    assert find(rows, "OAT") is not None


# --- H1: usage-based reorder point ------------------------------------------------

def test_H1_includes_three_days_safety_stock(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("LOW", "dairy").item("OK", "dairy")
    # point = 10 x (2 + 3) = 50. A 2-day cushion gives <= 41.4, a 4-day one >= 57.9.
    sc.steady("MKT", "LOW", 10, 45)
    sc.steady("MKT", "OK", 10, 55)
    rows = rows_json(tmp_path, sc)
    assert find(rows, "LOW") is not None
    assert find(rows, "OK") is None


def test_H1_usage_is_last_28_days_not_all_history(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.stock("MKT", "OAT", 25, 31 * 30 + 28 * 2)
    sc.daily("MKT", "OAT", "sale", 30, first=-60, last=-30)  # busy summer, long ago
    sc.daily("MKT", "OAT", "sale", 2, first=-28, last=-1)    # 2/day now -> point 10
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT") is None


def test_H1_usage_window_is_four_weeks_not_one(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.stock("MKT", "OAT", 10, 21 * 8)
    sc.daily("MKT", "OAT", "sale", 8, first=-28, last=-8)  # 6/day over 28 days -> point >= 12; 0/day over 7
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT") is not None


# --- H2: usage is sales + waste only ------------------------------------------------

def test_H2_transfers_and_returns_are_not_usage(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.stock("MKT", "OAT", 20, 120 + 400 + 100)
    sc.daily("MKT", "OAT", "sale", 2)                      # usage 2/day -> point <= 14.5 for any cushion
    sc.move(-10, "MKT", "OAT", "transfer_out", 400, "T1")  # if counted: ~20/day -> point >= 38
    sc.move(-10, "HAR", "OAT", "transfer_in", 400, "T1")
    sc.move(-5, "MKT", "OAT", "return", 100, "R1")
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT") is None


def test_H2_waste_counts_as_usage(tmp_path):
    sc = Scenario().supplier("bakery", 10).item("DOUGH", "bakery")
    sc.stock("MKT", "DOUGH", 35, 60 * 4)
    sc.daily("MKT", "DOUGH", "sale", 2)
    sc.daily("MKT", "DOUGH", "waste", 2)                   # 4/day -> point >= 38.6; sales only -> <= 31
    rows = rows_json(tmp_path, sc)
    assert find(rows, "DOUGH") is not None


def test_H2_transfers_in_do_not_offset_usage(tmp_path):
    sc = Scenario().supplier("dairy", 10).item("OAT", "dairy")
    sc.stock("STN", "OAT", 300, 200)
    sc.move(-3, "STN", "OAT", "transfer_out", 200, "T2")
    sc.move(-3, "MKT", "OAT", "transfer_in", 200, "T2")
    sc.stock("MKT", "OAT", 70, 600 - 200)
    sc.daily("MKT", "OAT", "sale", 10)                     # 10/day -> point >= 96; net of transfer -> <= 56
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT") is not None


# --- H3: whole cases ------------------------------------------------------------------

def _whole_cases(qty, case, shortfall):
    return qty is not None and qty % case == 0 and qty >= shortfall


def test_H3_quantity_is_whole_cases(tmp_path):
    # Out of stock: listed under any cushion; shortfall is at least lead x usage.
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy", case=12).item("MILK", "dairy", case=6)
    sc.steady("MKT", "OAT", 10, 0)
    sc.steady("MKT", "MILK", 7, 0)
    rows = rows_json(tmp_path, sc)
    assert _whole_cases(find(rows, "OAT"), 12, 2 * 10 * LO), find(rows, "OAT")
    assert _whole_cases(find(rows, "MILK"), 6, 2 * 7 * LO), find(rows, "MILK")


def test_H3_small_need_rounds_up_to_a_full_case(tmp_path):
    # Needs 9-30 units under any cushion/cover; the case is 48, so rounding down
    # or to nearest gives 0.
    sc = Scenario().supplier("roaster", 2).item("DECAF", "roaster", case=48)
    sc.steady("MKT", "DECAF", 1, 0)
    rows = rows_json(tmp_path, sc)
    assert _whole_cases(find(rows, "DECAF"), 48, 2 * LO), find(rows, "DECAF")


# --- H4: order up to lead time + 14 days of usage, no more ------------------------------

def test_H4_order_covers_lead_time_plus_two_weeks(tmp_path):
    sc = Scenario().supplier("dairy", 3).item("OAT", "dairy")
    sc.steady("MKT", "OAT", 10, 20)
    qty = find(rows_json(tmp_path, sc), "OAT")
    lo, hi = target_range(10, 3, 20)                        # about 17 x 10 - 20 = 150
    assert qty is not None and lo <= qty <= hi, qty


def test_H4_cap_depends_on_lead_time(tmp_path):
    sc = Scenario().supplier("mill", 6).item("FLOUR", "mill")
    sc.steady("MKT", "FLOUR", 5, 12)
    qty = find(rows_json(tmp_path, sc), "FLOUR")
    lo, hi = target_range(5, 6, 12)                         # about 20 x 5 - 12 = 88
    assert qty is not None and lo <= qty <= hi, qty


# --- H5: per shop -------------------------------------------------------------------------

def test_H5_each_shop_judged_on_its_own_stock(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy", min_stock=20)
    sc.steady("MKT", "OAT", 10, 10)
    sc.stock("STN", "OAT", 200, 0)
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT", "MKT") is not None
    assert find(rows, "OAT", "STN") is None


def test_H5_one_line_per_shop_sized_by_its_usage(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.steady("MKT", "OAT", 10, 0)
    sc.steady("STN", "OAT", 4, 0)
    rows = rows_json(tmp_path, sc)
    mkt, stn = find(rows, "OAT", "MKT"), find(rows, "OAT", "STN")
    assert mkt is not None and stn is not None
    assert mkt > stn
    assert find(rows, "OAT", "HAR") is None


def test_H5_another_shops_order_does_not_cover(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.steady("MKT", "OAT", 10, 5)
    sc.po("STN", "OAT", 100)
    rows = rows_json(tmp_path, sc)
    assert find(rows, "OAT", "MKT") is not None


# --- T1: min_stock is ignored -------------------------------------------------------------

def test_T1_high_min_stock_does_not_trigger(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy", min_stock=100)
    sc.steady("MKT", "OAT", 2, 60)                          # point 10, plenty
    assert find(rows_json(tmp_path, sc), "OAT") is None


def test_T1_low_min_stock_does_not_hide_need(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy", min_stock=5)
    sc.steady("MKT", "OAT", 10, 10)                         # point >= 19 for any cushion
    assert find(rows_json(tmp_path, sc), "OAT") is not None


# --- T2: open purchase orders count toward cover ------------------------------------------

def test_T2_open_order_covers_need(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.steady("MKT", "OAT", 10, 5)
    sc.po("MKT", "OAT", 400)                                # covers 40 days
    assert find(rows_json(tmp_path, sc), "OAT") is None


def test_T2_cancelled_and_received_orders_do_not_count(tmp_path):
    sc = Scenario().supplier("dairy", 2).item("OAT", "dairy")
    sc.steady("MKT", "OAT", 10, 5)
    sc.po("MKT", "OAT", 100, status="cancelled")
    sc.po("MKT", "OAT", 100, status="received")  # its delivery is already in on-hand
    assert find(rows_json(tmp_path, sc), "OAT") is not None


def test_T2_open_order_reduces_quantity(tmp_path):
    # Lead 6: point >= 57 under any cushion, so both are listed (BBB cover is 40).
    sc = Scenario().supplier("dairy", 6).item("AAA", "dairy").item("BBB", "dairy")
    sc.steady("MKT", "AAA", 10, 0)
    sc.steady("MKT", "BBB", 10, 0)
    sc.po("MKT", "BBB", 40)
    rows = rows_json(tmp_path, sc)
    a, b = find(rows, "AAA"), find(rows, "BBB")
    assert a is not None and b is not None
    assert 38 <= a - b <= 42
