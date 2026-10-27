#!/usr/bin/env python3
"""Check that this task discriminates.

- ref passes every hidden test and the repo's own tests;
- naive passes every E test and fails at least one test of every H/T id;
- the bare repo fails every hidden test;
- one mutant per H/T id (ref with only that rule broken) fails that id and
  nothing else.

There's no load-or-failure item in this task, so there's no time budget to
measure; the loop tests (H3) carry their own 5-second alarm.
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
ACCESS = "folio/access.py"

# id -> list of (old, new) replacements applied to ref's folio/access.py
MUTANTS = {
    "H1": [(
        "                best = max(best, RANK[role])\n    return best",
        "                best = max(best, RANK[role])\n        if best:\n            return best  # nearest grant wins\n    return best",
    )],
    "H2": [("    if store.get_workspace(resource.workspace_id).is_admin(user_id):\n        return True\n", "")],
    "H3": [(
        "        frontier.extend(g.id for g in store.groups.values() if gid in g.subgroups)\n",
        "        pass  # groups are flat\n",
    )],
    "H4": [("    if action == \"share\" and restricted:\n        return False  # only the owner passes on a restricted doc\n", "")],
    "H5": [("    if not user.active:\n        return False\n", "")],
    "H6": [  # the obvious rule: guests inherit like anyone else, capped at commenter
        ("    if guest:\n", "    if False:\n"),
        ("                best = max(best, RANK[role])\n    return best\n",
         "                best = max(best, RANK[role])\n    return min(best, RANK[GUEST_CAP]) if guest else best\n"),
    ],
    "H7": [("    if isinstance(resource, Document) and resource.trashed:\n        return owner\n", "")],
    "H8": [("    if HR_FOLDER in names and not _in_group_named(store, user_id, HR_GROUP):\n        return False\n", "")],
    "H9": [("        best = min(best, RANK[\"commenter\"])  # issued work is frozen\n", "        pass\n")],
    "T1": [(
        "    store.grants.setdefault(resource_id, {})[principal_id] = role\n",
        "    shares = store.grants.setdefault(resource_id, {})\n"
        "    shares[principal_id] = max(shares.get(principal_id, role), role, key=RANK.get)\n",
    )],
    "T2": [(
        "    shares = store.grants.get(resource_id, {})\n",
        "    shares = store.grants.get(resource_id, {})\n"
        "    if store.kind_of(principal_id) is ResourceKind.GROUP:\n"
        "        for uid in store.get_group(principal_id).members:\n"
        "            shares.pop(uid, None)\n",
    )],
}


def build(overlay, patches=None):
    tmp = Path(tempfile.mkdtemp(prefix="doc-sharing-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    for old, new in patches or ():
        target = tmp / ACCESS
        text = target.read_text()
        assert text.count(old) == 1, f"mutant patch does not apply cleanly: {old!r}"
        target.write_text(text.replace(old, new))
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, target):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", target],
        cwd=cwd, capture_output=True, text=True, timeout=300,
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
    hidden_ids = [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    ids += hidden_ids
    problems = []

    dirs = {"ref": build("ref"), "naive": build("naive"), "repo": build(None)}
    missing = sorted(set(hidden_ids) - set(MUTANTS))
    if missing:
        problems.append(f"no mutant for {missing}")
    for mid, patches in MUTANTS.items():
        dirs[f"m{mid}"] = build("ref", patches)
    try:
        ref_existing = run(dirs["ref"], "tests").returncode == 0
        naive_existing = run(dirs["naive"], "tests").returncode == 0
        res = {name: by_id(hidden_results(d)) for name, d in dirs.items()}
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

    print()
    print("mutant  fails                ok")
    for mid in MUTANTS:
        m = res[f"m{mid}"]
        failing = sorted(i for i, oks in m.items() if not all(oks))
        ok = failing == [mid]
        if not ok:
            problems.append(f"mutant {mid} fails {failing}")
        print(f"{mid:<8}{','.join(failing) or '-':<21}{'yes' if ok else 'NO'}")

    print(f"existing tests: ref {'pass' if ref_existing else 'FAIL'}, naive {'pass' if naive_existing else 'FAIL'}")
    if not (ref_existing and naive_existing):
        problems.append("existing tests")
    print("timing: none (no load-or-failure item); H3 loop tests use a 5 s alarm")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
