#!/usr/bin/env python3
"""Check that this task discriminates:
- ref passes every hidden test and the repo's own tests;
- naive passes every E test and fails at least one test of every H/T id;
- the bare repo fails every hidden test;
- each mutant (ref with one H/T item broken) fails only its own id;
- timing: ref's 200k-row import uses at most 1/5 of the CPU budget, and a
  commit-per-row import (naive, measured on 20k rows) is far over it."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "test_hidden.py"
META = json.loads((HERE / "meta.json").read_text())
MUTANTS = sorted(p.name for p in (HERE / "mutants").iterdir() if p.is_dir())


def build(*overlays):
    tmp = Path(tempfile.mkdtemp(prefix="bank-import-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    for overlay in overlays:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
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
        results = {n: False for n in names}
    return results


def by_id(results):
    groups = defaultdict(list)
    for name, ok in results.items():
        groups[name.split("_")[1]].append(ok)
    return groups


def timing(cwd, rows, label):
    """CPU seconds of one fresh import and one re-import of the hidden tests' big export."""
    script = f"""
import sys, tempfile, pathlib
sys.path.insert(0, {str(cwd)!r})
import test_hidden as h
path = h.make_big_export(pathlib.Path(tempfile.mkdtemp()) / "big.csv", {rows})
tmp = pathlib.Path(tempfile.mkdtemp())
h.big_setup(tmp)
first = h.timed_import(tmp, path, "Northbank")
again = h.timed_import(tmp, path, "Northbank")
print(first, again, h.count(tmp, "Northbank"))
"""
    proc = subprocess.run([sys.executable, "-c", script], cwd=cwd, capture_output=True, text=True,
                          timeout=900)
    if proc.returncode != 0:
        print(f"timing {label}: FAILED\n{proc.stderr[-2000:]}")
        return None
    first, again, n = proc.stdout.split()
    return float(first), float(again), int(n)


def main():
    ids = [e["id"] for e in META["explicit_requirements"]]
    ids += [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    problems = []
    spec = importlib.util.spec_from_file_location("h", HIDDEN)
    hidden_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hidden_mod)
    budget = hidden_mod.BUDGET_CPU

    dirs = {"ref": build("ref"), "naive": build("naive"), "repo": build()}
    for m in MUTANTS:
        dirs[f"mutant {m}"] = build("ref", f"mutants/{m}")
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {k: pool.submit(hidden_results, d) for k, d in dirs.items()}
            existing = {k: pool.submit(run, dirs[k], "tests") for k in ("ref", "naive")}
            res = {k: by_id(f.result()) for k, f in futures.items()}
            existing_ok = {k: f.result().returncode == 0 for k, f in existing.items()}
        runs = [timing(dirs["ref"], 200_000, "ref") for _ in range(3)]
        ref_time = None if None in runs else min(runs, key=lambda t: max(t[:2]))
        naive_time = timing(dirs["naive"], 20_000, "naive (20k rows)")
    finally:
        for d in dirs.values():
            shutil.rmtree(d, ignore_errors=True)

    r, n, b = res["ref"], res["naive"], res["repo"]

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

    for m in MUTANTS:
        mres = res[f"mutant {m}"]
        failing = sorted(i for i in ids if not all(mres.get(i, [False])))
        ok = failing == [m]
        print(f"mutant {m}: fails {failing}  {'ok' if ok else 'NO'}")
        if not ok:
            problems.append(f"mutant {m} fails {failing}")
    missing = [i for i in ids if not i.startswith("E") and i not in MUTANTS]
    if missing:
        problems.append(f"no mutant for {missing}")

    print(f"existing tests: ref {'pass' if existing_ok['ref'] else 'FAIL'}, "
          f"naive {'pass' if existing_ok['naive'] else 'FAIL'}")
    if not all(existing_ok.values()):
        problems.append("existing tests")

    if ref_time is None:
        problems.append("ref timing")
    else:
        first, again, count = ref_time
        ok = max(first, again) * 5 <= budget and count == 200_000
        print(f"timing ref 200k rows: import {first:.2f}s, re-import {again:.2f}s CPU; "
              f"budget {budget:.1f}s (needs 5x headroom: {'ok' if ok else 'NO'})")
        if not ok:
            problems.append("ref timing headroom")
    if naive_time is None:
        problems.append("naive timing")
    else:
        first, again, _ = naive_time
        est = first * 10
        ok = est > budget
        print(f"timing naive 20k rows: import {first:.2f}s CPU -> about {est:.0f}s for 200k "
              f"({'over budget, ok' if ok else 'NO: within budget'})")
        if not ok:
            problems.append("naive timing")

    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
