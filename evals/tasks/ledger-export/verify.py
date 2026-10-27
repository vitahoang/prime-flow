#!/usr/bin/env python3
"""Check that the ledger-export task discriminates.

ref   overlay: every hidden test and every existing test passes.
naive overlay: every E test passes; every H/T id has at least one failure.
repo  alone:   hidden tests fail.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "test_hidden.py"


def build(overlay):
    tmp = Path(tempfile.mkdtemp(prefix="ledger-export-"))
    dest = tmp / "repo"
    shutil.copytree(HERE / "repo", dest, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    if overlay:
        shutil.copytree(HERE / overlay, dest, dirs_exist_ok=True)
    return dest


def pytest(repo, target):
    xml = repo.parent / "report.xml"
    env = dict(os.environ, TASK_REPO=str(repo))
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    f"--junitxml={xml}", str(target)],
                   cwd=repo, env=env, capture_output=True)
    results = {}
    for case in ET.parse(xml).getroot().iter("testcase"):
        failed = any(c.tag in ("failure", "error") for c in case)
        results[case.get("name")] = not failed
    return results


def by_id(results):
    grouped = defaultdict(dict)
    for name, ok in results.items():
        m = re.match(r"test_([EHT]\d+)_", name)
        grouped[m[1] if m else "?"][name] = ok
    return grouped


def main():
    ref_repo, naive_repo, bare_repo = build("ref"), build("naive"), build(None)
    ref_h, naive_h, bare_h = (pytest(r, HIDDEN) for r in (ref_repo, naive_repo, bare_repo))
    ref_existing = pytest(ref_repo, ref_repo / "tests")
    bare_existing = pytest(bare_repo, bare_repo / "tests")

    problems = []
    ref_g, naive_g, bare_g = by_id(ref_h), by_id(naive_h), by_id(bare_h)
    ids = sorted(ref_g, key=lambda i: ("EHT?".index(i[0]), int(i[1:]) if i[1:].isdigit() else 0))

    print(f"{'id':<4} {'tests':>5}  {'ref':<8} {'naive':<10} {'repo':<8} ok")
    for i in ids:
        n = len(ref_g[i])
        rp = sum(ref_g[i].values())
        npass = sum(naive_g[i].values())
        bp = sum(bare_g[i].values())
        ok = rp == n
        if i.startswith("E"):
            ok = ok and npass == n
            need = 1
        else:
            ok = ok and npass < n
            need = 2
        if n < need:
            ok = False
        ok = ok and bp == 0
        if not ok:
            problems.append(i)
        print(f"{i:<4} {n:>5}  {rp}/{n:<6} {npass}/{n:<8} {bp}/{n:<6} {'yes' if ok else 'NO'}")

    ex_ok = all(ref_existing.values()) and all(bare_existing.values())
    print(f"existing tests: repo {sum(bare_existing.values())}/{len(bare_existing)}, "
          f"ref {sum(ref_existing.values())}/{len(ref_existing)}")
    if not ex_ok:
        problems.append("existing")
    if "?" in ref_g:
        problems.append("unnamed tests: " + ", ".join(ref_g["?"]))

    for r in (ref_repo, naive_repo, bare_repo):
        shutil.rmtree(r.parent, ignore_errors=True)
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
