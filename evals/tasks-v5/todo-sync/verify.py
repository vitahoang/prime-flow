#!/usr/bin/env python3
"""Check that this task discriminates.

- ref passes every hidden test and the repo's own tests;
- naive passes every E test and fails at least one test of every H/T id;
- the bare repo fails every hidden test;
- one mutant per H/T id (ref with just that rule broken) fails at least one
  test of its own id and passes every other id.

No time budget in this task, so there are no timing checks.
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

# id -> list of (file under ref/, old text, new text)
MUTANTS = {
    "T1": [("tickoff/replica.py",
            "return (change.lamport, change.device)",
            "return (change.wall, change.device)")],
    "H1": [("tickoff/replica.py",
            "            for name, value in change.fields.items():\n"
            "                cur = meta[\"fields\"].get(name)\n",
            "            whole = max((tuple(s) for s in meta[\"fields\"].values()), default=None)\n"
            "            for name, value in change.fields.items():\n"
            "                cur = whole\n")],
    "H2": [("tickoff/replica.py",
            "return latest is not None and latest > tuple(meta[\"deleted\"])",
            "return False")],
    "H3": [("tickoff/sync.py",
            "have = hub.head(replica.device_id)",
            "have = replica.sync_state.get(\"pushed_to\", 0)"),
           ("tickoff/sync.py",
            "    report.pushed = len(outgoing)\n",
            "    report.pushed = len(outgoing)\n"
            "    if outgoing:\n"
            "        replica.sync_state[\"pushed_to\"] = outgoing[-1].lamport\n")],
    "H5": [("tickoff/sync.py",
            "    if _in_work_list(replica, change):\n        return False\n",
            "")],
    "H6": [("tickoff/sync.py",
            "        return _only_ticks(change)",
            "        return True")],
    "H4": [("tickoff/replica.py",
            "return (task.order, self._order_device(task.id), task.id)",
            "return (task.order, task.title.lower(), task.id)")],
}


def build(overlay, patches=()):
    tmp = Path(tempfile.mkdtemp(prefix="todo-sync-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    for rel, old, new in patches:
        path = tmp / rel
        text = path.read_text()
        if text.count(old) != 1:
            raise SystemExit(f"mutant patch does not apply to {rel}: {old[:60]!r}")
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


def main():
    ids = [e["id"] for e in META["explicit_requirements"]]
    ids += [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    problems = []

    dirs = {"ref": build("ref"), "naive": build("naive"), "repo": build(None)}
    for mid, patches in MUTANTS.items():
        dirs[f"mut-{mid}"] = build("ref", patches)
    try:
        res = {name: by_id(hidden_results(d)) for name, d in dirs.items()}
        ref_existing = run(dirs["ref"], "tests").returncode == 0
        naive_existing = run(dirs["naive"], "tests").returncode == 0
    finally:
        for d in dirs.values():
            shutil.rmtree(d, ignore_errors=True)

    def cell(oks):
        return f"{sum(oks)}/{len(oks)}"

    r, n, b = res["ref"], res["naive"], res["repo"]
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

    hidden_ids = [i for i in ids if not i.startswith("E")]
    missing = [i for i in hidden_ids if i not in MUTANTS]
    if missing:
        problems.append(f"no mutant for {missing}")
    for mid in MUTANTS:
        m = res[f"mut-{mid}"]
        failing = sorted(i for i in ids if not all(m.get(i, [False])))
        ok = failing == [mid]
        print(f"mutant {mid}: fails {failing}  {'ok' if ok else 'NO'}")
        if not ok:
            problems.append(f"mutant {mid} fails {failing}")

    print(f"existing tests: ref {'pass' if ref_existing else 'FAIL'}, naive {'pass' if naive_existing else 'FAIL'}")
    if not (ref_existing and naive_existing):
        problems.append("existing tests")
    print("timing: no time budget in this task")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
