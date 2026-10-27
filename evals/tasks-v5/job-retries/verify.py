#!/usr/bin/env python3
"""Check that this task discriminates: ref passes everything, naive passes E but
fails every H/T, the bare repo fails the hidden tests, and each one-item mutant
of ref fails only its own id. Also checks that the T1 race tests are reliable
(ref always passes, the non-atomic claim always fails) and that the hidden
suite runs in reasonable time."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE / "hidden" / "test_hidden.py"
META = json.loads((HERE / "meta.json").read_text())

# One mutant per H/T id: ref with only that item broken (file, old text, new text).
MUTANTS = {
    "T1": ("taskmill/store.py",
           ' WHERE id = ? AND status = ? AND attempts = ?",\n'
           '                (now, worker_id, now, row["id"], row["status"], row["attempts"]),',
           ' WHERE id = ?",\n                (now, worker_id, now, row["id"]),'),
    "H1": ("taskmill/store.py", "LEASE_SECONDS = 600.0", "LEASE_SECONDS = 1e12"),
    "H2": ("taskmill/retry.py", "base: float = 30.0", "base: float = 10.0"),
    "H3": ("taskmill/retry.py", "max_attempts: int = 5", "max_attempts: int = 3"),
    "H4": ("taskmill/retry.py", "        if isinstance(exc, PermanentError):\n            return None\n", ""),
    "H5": ("taskmill/retry.py", "delay = max(delay, exc.retry_after)", "pass"),
    "H6": ("taskmill/store.py", "self._finish(job_id, now, Status.DEAD, error)",
           "self._finish(job_id, now, Status.FAILED, error)"),
    "H7": ("taskmill/worker.py", 'self.metrics.incr("jobs.unknown_kind")\n            self._failed(job, exc)',
           'self.metrics.incr("jobs.unknown_kind")\n            self._give_up(job, self.clock.now(), str(exc))'),
    "H8": ("taskmill/worker.py", "if job.kind in NO_ALERT_KINDS or (", "if True or ("),
    "H9": ("taskmill/worker.py", 'NO_RETRY_KINDS = frozenset({"image.thumbnail"})', "NO_RETRY_KINDS = frozenset()"),
}
RACE_RUNS = 3          # T1 is a real race: repeat it to check it's reliable
SUITE_BUDGET = 90.0    # seconds for the whole hidden suite on ref


def build(overlay, mutant=None):
    tmp = Path(tempfile.mkdtemp(prefix="job-retries-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    if mutant:
        path, old, new = MUTANTS[mutant]
        f = tmp / path
        text = f.read_text()
        assert text.count(old) == 1, f"mutant {mutant}: pattern not found exactly once in {path}"
        f.write_text(text.replace(old, new))
    shutil.copy(HIDDEN, tmp / "test_hidden.py")
    return tmp


def run(cwd, *target):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *target],
        cwd=cwd, capture_output=True, text=True,
    )


def hidden_results(cwd, *extra):
    proc = run(cwd, "test_hidden.py", *extra)
    results = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"(PASSED|FAILED|ERROR) test_hidden\.py::(test_\w+)", line)
        if m:
            results[m.group(2)] = m.group(1) == "PASSED"
    if not results and not extra:
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

    dirs = {"ref": build("ref"), "naive": build("naive"), "bare": build(None)}
    for m in MUTANTS:
        dirs[f"mut-{m}"] = build("ref", m)
    try:
        t = time.monotonic()
        r = by_id(hidden_results(dirs["ref"]))
        suite_time = time.monotonic() - t
        n, b = by_id(hidden_results(dirs["naive"])), by_id(hidden_results(dirs["bare"]))
        muts = {m: by_id(hidden_results(dirs[f"mut-{m}"])) for m in MUTANTS}
        ref_existing = run(dirs["ref"], "tests").returncode == 0
        naive_existing = run(dirs["naive"], "tests").returncode == 0
        repo_existing = run(dirs["bare"], "tests").returncode == 0
        race = {k: [all(hidden_results(dirs[k], "-k", "T1").values()) for _ in range(RACE_RUNS)]
                for k in ("ref", "naive", "mut-T1")}
    finally:
        for d in dirs.values():
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

    for m, res in muts.items():
        failing = sorted(i for i in ids if not all(res.get(i, [False])))
        ok = failing == [m]
        print(f"mutant {m}: fails {failing}  {'ok' if ok else 'NO'}")
        if not ok:
            problems.append(f"mutant {m} fails {failing}")

    print(f"T1 race x{RACE_RUNS}: ref passes {race['ref']}, naive passes {race['naive']}, "
          f"mutant passes {race['mut-T1']}")
    if not all(race["ref"]) or any(race["naive"]) or any(race["mut-T1"]):
        problems.append("T1 race not reliable")

    print(f"hidden suite on ref: {suite_time:.1f}s (budget {SUITE_BUDGET:.0f}s)")
    if suite_time > SUITE_BUDGET:
        problems.append("hidden suite too slow")

    print(f"existing tests: repo {'pass' if repo_existing else 'FAIL'}, ref {'pass' if ref_existing else 'FAIL'}, "
          f"naive {'pass' if naive_existing else 'FAIL'}")
    if not (repo_existing and ref_existing and naive_existing):
        problems.append("existing tests")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
