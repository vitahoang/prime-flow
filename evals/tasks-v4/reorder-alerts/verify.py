#!/usr/bin/env python3
"""Check that this task discriminates: ref passes everything, naive passes E but
fails every H/T, and the bare repo fails the hidden tests."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "test_hidden.py"
META = json.loads((HERE / "meta.json").read_text())


def build(overlay):
    tmp = Path(tempfile.mkdtemp(prefix="reorder-alerts-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, target):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", target],
        cwd=cwd, capture_output=True, text=True,
    )
    return proc


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


def main():
    ids = [e["id"] for e in META["explicit_requirements"]]
    ids += [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    problems = []

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
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
