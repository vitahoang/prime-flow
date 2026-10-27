#!/usr/bin/env python3
"""Check that this task discriminates: ref passes everything, naive passes every E
test but fails at least one test of every H/T item, and the bare repo fails the
hidden tests. Prints a table of passed/total per requirement id."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
META = json.loads((HERE / "meta.json").read_text())
IDS = ([r["id"] for r in META["explicit_requirements"]]
       + [r["id"] for r in META["hidden_requirements"]]
       + [r["id"] for r in META["traps"]])


def build(overlay):
    tmp = Path(tempfile.mkdtemp(prefix="recurring-events-"))
    work = tmp / "repo"
    shutil.copytree(HERE / "repo", work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    if overlay:
        shutil.copytree(HERE / overlay, work, dirs_exist_ok=True)
    shutil.copytree(HERE / "hidden", work / "hidden_tests")
    return tmp, work


def pytest(work, target):
    xml = work / f"junit-{target.replace('/', '_')}.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", target],
        cwd=work, capture_output=True, text=True)
    results = {}
    if xml.exists():
        for case in ET.parse(xml).iter("testcase"):
            failed = any(child.tag in ("failure", "error") for child in case)
            skipped = any(child.tag == "skipped" for child in case)
            results[case.get("name")] = not (failed or skipped)
    return proc.returncode, results


def by_id(results, names):
    table = defaultdict(lambda: [0, 0])
    for name in names:
        m = re.match(r"test_([A-Z]\d+)_", name)
        if not m:
            continue
        table[m.group(1)][1] += 1
        if results.get(name, False):
            table[m.group(1)][0] += 1
    return table


def main():
    runs = {}
    for label, overlay in (("ref", "ref"), ("naive", "naive"), ("repo", None)):
        tmp, work = build(overlay)
        try:
            existing_rc, existing = pytest(work, "tests")
            _, hidden = pytest(work, "hidden_tests")
        finally:
            shutil.rmtree(tmp)
        runs[label] = (existing_rc, existing, hidden)

    names = sorted(runs["ref"][2])
    tables = {label: by_id(run[2], names) for label, run in runs.items()}
    unknown = sorted({i for i in tables["ref"]} - set(IDS))
    problems = []

    print(f"{'id':<5}{'tests':>6}  {'ref':>6}  {'naive':>6}  {'repo':>6}")
    for rid in IDS:
        total = tables["ref"][rid][1]
        cells = [f"{tables[l][rid][0]}/{total}" for l in ("ref", "naive", "repo")]
        print(f"{rid:<5}{total:>6}  {cells[0]:>6}  {cells[1]:>6}  {cells[2]:>6}")
        minimum = 1 if rid.startswith("E") else 2
        if total < minimum:
            problems.append(f"{rid}: only {total} test(s), need {minimum}")
        if tables["ref"][rid][0] != total:
            problems.append(f"{rid}: ref fails {total - tables['ref'][rid][0]} test(s)")
        if rid.startswith("E") and tables["naive"][rid][0] != total:
            problems.append(f"{rid}: naive fails an explicit test")
        if not rid.startswith("E") and tables["naive"][rid][0] == total:
            problems.append(f"{rid}: naive passes every test (does not discriminate)")
        if tables["repo"][rid][0]:
            problems.append(f"{rid}: bare repo passes {tables['repo'][rid][0]} hidden test(s)")
    for label, (rc, existing, _) in runs.items():
        ok = rc == 0 and existing and all(existing.values())
        print(f"existing tests with {label:<5}: {'pass' if ok else 'FAIL'} ({sum(existing.values())}/{len(existing)})")
        if not ok:
            problems.append(f"existing tests fail with {label}")
    if unknown:
        problems.append(f"tests reference ids missing from meta.json: {unknown}")
    if not names:
        problems.append("no hidden tests collected with ref")

    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK: task discriminates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
