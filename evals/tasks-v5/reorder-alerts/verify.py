#!/usr/bin/env python3
"""Check that this task discriminates:

- ref passes every hidden test and the existing tests;
- naive passes the E tests and fails at least one test of every H/T id;
- the bare repo fails every hidden test;
- one mutant per H/T id (ref with just that item broken) fails that id and no other;
- H8 timing: BUDGET_S (CPU seconds) in the hidden tests is at least 5x ref's CPU
  time on the big ledger, and a per-item scan, the per-(shop, item) mutant and
  naive all go over it.
"""

import importlib.util
import json
import os
import resource
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "test_hidden.py"
META = json.loads((HERE / "meta.json").read_text())
REORDER = "stockroom/reorder.py"

# id -> [(file, old, new)]: ref with exactly that item broken.
MUTANTS = {
    "H1": [(REORDER, "SAFETY_DAYS = 3", "SAFETY_DAYS = 0")],
    "H2": [(REORDER, "USAGE_TYPES = frozenset((MovementType.SALE, MovementType.WASTE))",
            "USAGE_TYPES = frozenset(t for t in MovementType if not t.is_inbound)")],
    "H3": [(REORDER, "case = supplier.case_size(sku)", "case = 1")],
    "H4": [(REORDER, "MAX_COVER_DAYS = 14", "MAX_COVER_DAYS = 7")],
    "H5": [(REORDER, "on_order = coming.get((s, sku), 0.0)",
            "on_order = sum(q for (_, k), q in coming.items() if k == sku)")],
    "H6": [(REORDER, "wait, point, case, qty, supplier.on_hold))", "wait, point, case, qty, False))")],
    "H7": [(REORDER, "wait = days_to_delivery(supplier, today)", "wait = supplier.lead_time_days")],
    "H8": [(REORDER, "from .ledger import window", "from .ledger import filter_movements, window"),
           (REORDER, "usage = used.get((s, sku), 0.0) / span",
            "usage = sum(m.qty for m in filter_movements(inv.movements, shop=s, sku=sku, "
            "since=window(today, USAGE_DAYS)[0], until=today, types=USAGE_TYPES) "
            "if not is_catering(m)) / span")],
    "H9": [(REORDER, 'return m.type is MovementType.SALE and "catering" in m.note.lower()', "return False")],
    "H10": [(REORDER, "        if open_days < USAGE_DAYS:\n", "        if False:\n")],
    "T1": [(REORDER, "            if cover >= point:\n",
            "            point = max(point, item.min_stock)\n            if cover >= point:\n"),
           (REORDER, "- cover\n", "- cover\n            target = max(target, item.min_stock - cover)\n")],
    "T2": [(REORDER, "if po.is_open():", "if po.status.value != 'received':")],
}

# Not an id: ref scanning the ledger once per item (not per shop and item).
# H8's budget must still catch it.
PER_ITEM = [
    (REORDER, "from .ledger import window", "from .ledger import filter_movements, window"),
    (REORDER, "Key = Tuple[str, str]\n",
     "Key = Tuple[str, str]\n_ITEM_MOVES = {}\n\n\n"
     "def _item_usage(inv, today, sku):\n"
     "    if sku not in _ITEM_MOVES:\n"
     "        _ITEM_MOVES[sku] = filter_movements(inv.movements, sku=sku, "
     "since=window(today, USAGE_DAYS)[0], until=today, types=USAGE_TYPES)\n"
     "    return _ITEM_MOVES[sku]\n"),
    (REORDER, "usage = used.get((s, sku), 0.0) / span",
     "usage = sum(m.qty for m in _item_usage(inv, today, sku) "
     "if m.shop == s and not is_catering(m)) / span"),
]


def build(overlay, mutations=()):
    tmp = Path(tempfile.mkdtemp(prefix="reorder-alerts-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    for rel, old, new in mutations:
        path = tmp / rel
        text = path.read_text()
        assert text.count(old) == 1, f"mutation does not apply once: {old!r}"
        path.write_text(text.replace(old, new))
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, target):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", target],
        cwd=cwd, capture_output=True, text=True,
    )


def hidden_results(cwd):
    proc = run(cwd, "test_hidden.py")
    results = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"(PASSED|FAILED|ERROR) test_hidden\.py::(test_\w+)", line)
        if m:
            results[m.group(2)] = m.group(1) == "PASSED"
    if not results:
        names = re.findall(r"^def (test_\w+)", HIDDEN.read_text(), re.M)
        results = {n: False for n in names}  # import/collection failure
    return results


def by_id(results):
    groups = defaultdict(list)
    for name, ok in results.items():
        groups[name.split("_")[1]].append(ok)
    return groups


def hidden_module():
    spec = importlib.util.spec_from_file_location("hidden_tests", HIDDEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def time_reorder(cwd, data, today, timeout):
    """CPU seconds (user + sys) of one run, as the hidden H8 tests measure it."""
    env = dict(os.environ, STOCKROOM_DATA=str(data), STOCKROOM_TODAY=today, PYTHONPATH=str(cwd))
    start = cpu_of_children()
    try:
        proc = subprocess.run([sys.executable, "-m", "stockroom", "reorder", "--json"], cwd=cwd,
                              env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return float("inf")
    assert proc.returncode == 0, proc.stderr
    return cpu_of_children() - start


def cpu_of_children():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def timing(problems):
    mod = hidden_module()
    budget = mod.BUDGET_S
    data_root = Path(tempfile.mkdtemp(prefix="reorder-big-"))
    ref, slow, naive = build("ref"), build("ref", MUTANTS["H8"]), build("naive")
    per_item = build("ref", PER_ITEM)
    try:
        data = mod.big_ledger(data_root / "data")
        today = mod.TODAY.isoformat()
        time_reorder(ref, data, today, 120)  # warm the file cache
        ref_t = statistics.median(time_reorder(ref, data, today, 120) for _ in range(3))
        wall = mod.WALL_TIMEOUT_S
        per_item_t = time_reorder(per_item, data, today, wall)
        slow_t = time_reorder(slow, data, today, wall)
        naive_t = time_reorder(naive, data, today, wall)
    finally:
        for d in (data_root, ref, slow, naive, per_item):
            shutil.rmtree(d, ignore_errors=True)
    fmt = lambda t: f"> {wall}s wall" if t == float("inf") else f"{t:.1f}s"
    print(f"H8 CPU timing: budget {budget:.0f}s; ref median {ref_t:.1f}s "
          f"(headroom {budget / ref_t:.1f}x); per-item scan {fmt(per_item_t)}; "
          f"per-(shop, item) mutant {fmt(slow_t)}; naive {fmt(naive_t)}")
    if budget < 5 * ref_t:
        problems.append("H8 budget under 5x ref")
    if per_item_t <= budget:
        problems.append("H8 per-item scan within budget")
    if slow_t <= budget:
        problems.append("H8 per-item mutant within budget")
    if naive_t <= budget:
        problems.append("naive within H8 budget")


def main():
    ids = [e["id"] for e in META["explicit_requirements"]]
    ht_ids = [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    ids += ht_ids
    problems = []

    if set(MUTANTS) != set(ht_ids):
        problems.append(f"mutants do not match H/T ids: {sorted(set(MUTANTS) ^ set(ht_ids))}")

    ref = build("ref")
    naive = build("naive")
    bare = build(None)
    try:
        ref_existing = run(ref, "tests").returncode == 0
        naive_existing = run(naive, "tests").returncode == 0
        r, n, b = by_id(hidden_results(ref)), by_id(hidden_results(naive)), by_id(hidden_results(bare))
    finally:
        for d in (ref, naive, bare):
            shutil.rmtree(d, ignore_errors=True)

    def cell(oks):
        return f"{sum(oks)}/{len(oks)}"

    print(f"{'id':<5}{'tests':>6}  {'ref':>6}  {'naive':>6}  {'repo':>6}  ok")
    for i in ids:
        rr, nn, bb = r.get(i, []), n.get(i, []), b.get(i, [])
        ok = bool(rr) and all(rr) and not any(bb)
        if i.startswith("E"):
            ok = ok and all(nn)
        else:
            ok = ok and not all(nn) and len(rr) >= 2
        if not ok:
            problems.append(i)
        print(f"{i:<5}{len(rr):>6}  {cell(rr):>6}  {cell(nn):>6}  {cell(bb):>6}  {'yes' if ok else 'NO'}")
    stray = set(r) - set(ids)
    if stray:
        problems.append(f"tests with unknown ids: {sorted(stray)}")
    print(f"existing tests: ref {'pass' if ref_existing else 'FAIL'}, naive {'pass' if naive_existing else 'FAIL'}")
    if not (ref_existing and naive_existing):
        problems.append("existing tests")

    print("\nmutants (one per H/T id; must fail only its own id):")
    for mid in ht_ids:
        tmp = build("ref", MUTANTS.get(mid, []))
        try:
            m = by_id(hidden_results(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        failing = sorted(i for i, oks in m.items() if not all(oks))
        ok = failing == [mid]
        print(f"  {mid}: fails {', '.join(failing) or 'nothing'}  {'yes' if ok else 'NO'}")
        if not ok:
            problems.append(f"mutant {mid} fails {failing}")

    print()
    timing(problems)
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
