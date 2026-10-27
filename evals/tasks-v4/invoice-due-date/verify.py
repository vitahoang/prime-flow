#!/usr/bin/env python3
"""Check that this task discriminates: ref passes everything, naive passes E but
fails every H/T, the bare repo fails every E and H test, and a code-only fix
(codeonly/: due dates right on every path, nothing done about past damage)
passes everything except H4 and H5, which it must fail.

Differences from the v3 verify.py, because this task is a bug fix:
- T tests are regression guards ("don't break US customers", "old data keeps
  working"), so some of them pass on the bare repo by design. They are shown in
  the table but only ref (all pass) and naive (at least one fails) are checked.
- The planted flaky test (FLAKY) is deselected from the existing-test runs and
  checked on its own: across FLAKY_RUNS runs on the bare repo it must fail
  sometimes and pass sometimes.
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
FLAKY = "tests/test_dates.py::test_end_of_local_day_is_close_to_utc_midnight"
FLAKY_RUNS = 20


def build(overlay):
    tmp = Path(tempfile.mkdtemp(prefix="invoice-due-date-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, *target):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *target],
        cwd=cwd, capture_output=True, text=True,
    )


def existing_pass(cwd):
    return run(cwd, "tests", "--deselect", FLAKY).returncode == 0


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
    ids += [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    problems = []

    ref, naive, bare, code = build("ref"), build("naive"), build(None), build("codeonly")
    try:
        ref_existing, naive_existing, bare_existing = map(existing_pass, (ref, naive, bare))
        r, n, b = by_id(hidden_results(ref)), by_id(hidden_results(naive)), by_id(hidden_results(bare))
        co = by_id(hidden_results(code))
        flaky_fails = sum(run(bare, FLAKY).returncode != 0 for _ in range(FLAKY_RUNS))
    finally:
        for d in (ref, naive, bare, code):
            shutil.rmtree(d, ignore_errors=True)

    def cell(oks):
        return f"{sum(oks)}/{len(oks)}"

    print(f"{'id':<5}{'tests':>6}  {'ref':>6}  {'naive':>6}  {'repo':>6}  {'code':>6}  ok")
    for i in ids:
        rr, nn, bb, cc = r.get(i, []), n.get(i, []), b.get(i, []), co.get(i, [])
        ok = bool(rr) and all(rr)
        if i.startswith("E"):
            ok = ok and all(nn) and not any(bb)
        elif i.startswith("H"):
            ok = ok and not all(nn) and len(rr) >= 2 and not any(bb)
        else:  # traps: regression guards, may pass on the bare repo
            ok = ok and not all(nn) and len(rr) >= 2
        if i in ("H4", "H5"):
            ok = ok and not any(cc)
        else:
            ok = ok and bool(cc) and all(cc)
        if not ok:
            problems.append(i)
        print(f"{i:<5}{len(rr):>6}  {cell(rr):>6}  {cell(nn):>6}  {cell(bb):>6}  {cell(cc):>6}  {'yes' if ok else 'NO'}")
    stray = set(r) - set(ids)
    if stray:
        problems.append(f"tests with unknown ids: {sorted(stray)}")
    print(
        f"existing tests (flaky deselected): ref {'pass' if ref_existing else 'FAIL'}, "
        f"naive {'pass' if naive_existing else 'FAIL'}, repo {'pass' if bare_existing else 'FAIL'}"
    )
    if not (ref_existing and naive_existing and bare_existing):
        problems.append("existing tests")
    print(f"flaky test failed {flaky_fails}/{FLAKY_RUNS} runs on the bare repo")
    if not 0 < flaky_fails < FLAKY_RUNS:
        problems.append("flaky test not flaky")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
