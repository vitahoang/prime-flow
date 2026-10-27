#!/usr/bin/env python3
"""Check that this task discriminates.

- ref passes every hidden test and the repo's own tests;
- naive passes every E test and fails at least one test of every H/T id;
- the bare repo fails every hidden test;
- one mutant per H/T id (ref with only that item broken) fails that id and
  passes every other id.

No item in this task is load-or-failure, so there is no time budget to check.
"""

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


def build(*overlays):
    tmp = Path(tempfile.mkdtemp(prefix="usage-billing-"))
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


def main():
    ids = [e["id"] for e in META["explicit_requirements"]]
    ht = [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    ids += ht
    problems = []

    dirs = {"ref": build("ref"), "naive": build("naive"), "repo": build()}
    for i in ht:
        dirs[f"mutant {i}"] = build("ref", f"mutants/{i}")
    try:
        res = {name: by_id(hidden_results(d)) for name, d in dirs.items()}
        ref_existing = run(dirs["ref"], "tests").returncode == 0
        naive_existing = run(dirs["naive"], "tests").returncode == 0
        bare_existing = run(dirs["repo"], "tests").returncode == 0
    finally:
        for d in dirs.values():
            shutil.rmtree(d, ignore_errors=True)

    r, n, b = res["ref"], res["naive"], res["repo"]

    def cell(oks):
        return f"{sum(oks)}/{len(oks)}"

    print(f"{'id':<5}{'kind':<14}{'tests':>6}  {'ref':>6}  {'naive':>6}  {'repo':>6}  ok")
    kinds = {x["id"]: x.get("kind", "") for x in META["hidden_requirements"] + META["traps"]}
    for i in ids:
        rr, nn, bb = r.get(i, []), n.get(i, []), b.get(i, [])
        ok = bool(rr) and all(rr) and not any(bb)
        if i.startswith("E"):
            ok = ok and all(nn)
        else:
            ok = ok and not all(nn) and len(rr) >= 2
        if not ok:
            problems.append(i)
        print(f"{i:<5}{kinds.get(i, ''):<14}{len(rr):>6}  {cell(rr):>6}  {cell(nn):>6}  {cell(bb):>6}  {'yes' if ok else 'NO'}")
    stray = set(r) - set(ids)
    if stray:
        problems.append(f"tests with unknown ids: {sorted(stray)}")

    for i in ht:
        m = res[f"mutant {i}"]
        failing = sorted(x for x in ids if not all(m.get(x, [False])))
        good = failing == [i]
        print(f"mutant {i:<4} fails {failing}: {'ok' if good else 'NO'}")
        if not good:
            problems.append(f"mutant {i} fails {failing}")

    print(f"existing tests: repo {'pass' if bare_existing else 'FAIL'}, ref {'pass' if ref_existing else 'FAIL'}, "
          f"naive {'pass' if naive_existing else 'FAIL'}")
    if not (ref_existing and naive_existing and bare_existing):
        problems.append("existing tests")
    print("timing: n/a (no load-or-failure item)")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
