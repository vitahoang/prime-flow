#!/usr/bin/env python3
"""Check that this task discriminates.

- ref passes every hidden test and the repo's own tests;
- naive passes every E test and fails at least one test of every H/T id;
- the bare repo fails the hidden tests;
- one mutant per H/T id (ref with only that item broken) fails only that id;
- timing, as child-process CPU time (RUSAGE_CHILDREN): ref builds the
  20k-note index in <= 6s and answers a query in <= 200ms (5x headroom on
  30s / 1s); a correct stat-every-file-per-query design has 2x headroom;
  naive misses the budget.
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
SEARCH = "jotter/search.py"

# id -> [(old, new)] applied to ref's jotter/search.py
MUTANTS = {
    "H1": [("        if st.st_mtime_ns == self._dir_stamp:\n            return\n", ""),
           ("        self._dir_stamp = st.st_mtime_ns\n        seen = {}\n",
            "        self._dir_stamp = st.st_mtime_ns\n        self.docs = {}\n        seen = {}\n")],
    "H2": [("        if st.st_mtime_ns == self._dir_stamp:\n", "        if self._dir_stamp is not None:\n")],
    "H3": [("key=lambda s: (s[3], s[0], s[1])", "key=lambda s: (s[3], s[1], s[0])")],
    "H4": [("if required and not required <= doc.terms:", "if required and not required & doc.terms:"),
           ("        ok = True\n", "        ok = not q.terms\n"),
           ("                ok = False\n                break\n", "                continue\n            ok = True\n")],
    "H5": [("_QUERY = re.compile(r'(-?)\"([^\"]*)\"?|(\\S+)')", "_QUERY = re.compile(r'()()(\\S+)')"),
           ('            minus = "-" if bare.startswith("-") and len(bare) > 1 else ""\n', '            minus = ""\n')],
    "H6": [("        if doc.archived and not q.archived:\n", "        if False:\n")],
    "H7": [("    if text.isascii():\n        return text\n", "    return text\n")],
    "H8": [("        if PRIVATE in doc.tags and PRIVATE not in q.tags:\n            continue\n", "")],
    "H9": [("key=lambda s: (s[3], s[0], s[1])", "key=lambda s: (s[0], s[1])")],
    # Not an id: a correct design that stats every file on every query instead
    # of checking the folder's mtime. Timed below; it must pass the budget.
    "statall": [("        if st.st_mtime_ns == self._dir_stamp:\n            return\n", "")],
    "T1": [('return any(t == tag or t.startswith(tag + "/") for t in doc.tags)',
            'return any(t.lower() == tag.lower() or t.lower().startswith(tag.lower() + "/") for t in doc.tags)')],
}

TIMING = r'''
import shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
import test_hidden as t
big = t.make_big_vault(Path(tempfile.mkdtemp()) / "vault")
queries = (t._queries(big) * 2)[:t.N_QUERIES]
total, build, _ = t._child_cpu(big["root"], queries)
print(f"{build:.3f} {max(total - build, 0) / len(queries):.4f}")
shutil.rmtree(big["root"].parent, ignore_errors=True)
'''


def build(overlay, mutant=None):
    tmp = Path(tempfile.mkdtemp(prefix="notes-search-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    if mutant:
        path = tmp / SEARCH
        text = path.read_text()
        for old, new in MUTANTS[mutant]:
            assert text.count(old) == 1, f"mutant {mutant}: pattern not found once: {old!r}"
            text = text.replace(old, new)
        path.write_text(text)
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, target):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", target],
                          cwd=cwd, capture_output=True, text=True)


def hidden_results(cwd):
    proc = run(cwd, "test_hidden.py")
    for line in proc.stdout.splitlines():
        if line.startswith("E  ") and ("CPU" in line):
            print("      timing failure:", line[3:].strip()[:160])
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


def timing(cwd):
    proc = subprocess.run([sys.executable, "-c", TIMING], cwd=cwd, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    build_cpu, query_cpu = (float(x) for x in proc.stdout.split())
    return build_cpu, query_cpu


def main():
    ht = [h["id"] for h in META["hidden_requirements"]] + [t["id"] for t in META["traps"]]
    ids = [e["id"] for e in META["explicit_requirements"]] + ht
    problems = []
    dirs = []
    try:
        ref, naive, bare = build("ref"), build("naive"), build(None)
        dirs += [ref, naive, bare]
        ref_existing = run(ref, "tests").returncode == 0
        naive_existing = run(naive, "tests").returncode == 0
        r, n, b = by_id(hidden_results(ref)), by_id(hidden_results(naive)), by_id(hidden_results(bare))

        def cell(oks):
            return f"{sum(oks)}/{len(oks)}"

        print(f"{'id':<5}{'tests':>6}  {'ref':>6}  {'naive':>6}  {'repo':>6}  ok")
        for i in ids:
            rr, nn, bb = r.get(i, []), n.get(i, []), b.get(i, [])
            ok = bool(rr) and all(rr) and not any(bb)
            ok = ok and (all(nn) if i.startswith("E") else (not all(nn) and len(rr) >= 2))
            if not ok:
                problems.append(i)
            print(f"{i:<5}{len(rr):>6}  {cell(rr):>6}  {cell(nn):>6}  {cell(bb):>6}  {'yes' if ok else 'NO'}")
        stray = set(r) - set(ids)
        if stray:
            problems.append(f"tests with unknown ids: {sorted(stray)}")
        print(f"existing tests: ref {'pass' if ref_existing else 'FAIL'}, naive {'pass' if naive_existing else 'FAIL'}")
        if not (ref_existing and naive_existing):
            problems.append("existing tests")

        print("\nmutants (ref with one item broken):")
        for mid in ht:  # ids only; "statall" is timed below
            d = build("ref", mid)
            dirs.append(d)
            m = by_id(hidden_results(d))
            failing = sorted(i for i, oks in m.items() if not all(oks))
            ok = failing == [mid]
            if not ok:
                problems.append(f"mutant {mid} fails {failing}")
            print(f"  {mid}: fails {failing or 'nothing'}  {'yes' if ok else 'NO'}")

        print("\ntiming, 20k notes, child CPU seconds: build, per query (budget 30 / 1.0)")
        statall = build("ref", "statall")
        dirs.append(statall)
        rows = {"ref": timing(ref), "statall": timing(statall), "naive": timing(naive)}
        for name, (bc, qc) in rows.items():
            print(f"  {name:<8}{bc:7.3f} {qc:8.4f}")
        (rb, rq), (sb, sq), (nb, nq) = rows["ref"], rows["statall"], rows["naive"]
        if not (rb <= 6.0 and rq <= 0.2):
            problems.append("ref lacks 5x headroom on the CPU budget")
        if not (sb <= 10.0 and sq <= 0.5):
            problems.append("stat-every-file design lacks 2x headroom")
        if not (nb > 30 or nq > 1.0):
            problems.append("naive meets the CPU budget")
    finally:
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
