#!/usr/bin/env python3
"""Check that this task discriminates: ref passes everything, naive passes E but
fails every H/T, the bare repo fails the hidden tests, and each one-item mutant
of ref (ref with just that H/T item broken) fails only its own id."""

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
REF_DIGEST = "helpdesk/digest.py"
# One mutant per H/T id: text substitutions on ref's digest.py (each old string must
# occur exactly once). The mutant must fail a test of its id and pass every other id.
ID_MUTANTS = {
    "H1": [("if agent.is_away(today) or not agent.works_on(today):", "if not agent.works_on(today):")],
    "H2": [("now - waiting_since(t) > WINDOW", "now - t.updated_at > WINDOW")],
    "H3": [("    if not any(sections.values()):\n        return None\n", "")],
    "H4": [  # remembers sends on the store object only, so a new process forgets them
        ("        if any(n.key == key for n in history):",
         "        if key in store.__dict__.setdefault('_sent_' + agent.id, set()):"),
        ("        sent += 1", "        store.__dict__['_sent_' + agent.id].add(key)\n        sent += 1"),
    ],
    "H5": [("        if local.hour < SEND_HOUR_LOCAL:", "        if now.hour < 9:")],
    "H6": [
        ("now - waiting_since(t) > WINDOW],\n",
         "now - waiting_since(t) > WINDOW],\n        'resolved': [t.id for t in tickets if t.assignee == agent.id"
         " and t.resolved_at and since <= t.resolved_at <= now],\n"),
        ("TITLES = {", "TITLES = {'resolved': 'Resolved', "),
    ],
    "H7": [("if agent.is_away(today) or not agent.works_on(today):", "if agent.is_away(today):")],
    "H8": [("since=last, ", "since=None, ")],
    "H9": [("covering=_covering(store, agent, now))", "covering=None)")],
    "H10": [("    tickets = [t for t in tickets if not _muted(store, t)]\n", "")],
    "H13": [("    tickets = [t for t in tickets if not _internal(t)]\n", "")],
    "H14": [("    tickets = [t for t in tickets if not _legal(t)]\n", "")],
    "H11": [  # records the send before trying it
        ("        try:\n            mailer.send(render(digest, agent, store))\n        except MailerError:\n            continue\n"
         "        store.record_notification(Notification(kind=DIGEST, agent_id=agent.id, sent_at=now, key=key))\n",
         "        store.record_notification(Notification(kind=DIGEST, agent_id=agent.id, sent_at=now, key=key))\n"
         "        try:\n            mailer.send(render(digest, agent, store))\n        except MailerError:\n            continue\n"),
    ],
    "H12": [
        ("mine = sorted((t for t in tickets if t.assignee == agent.id and t.is_active), key=by_sla)",
         "mine = [t for t in tickets if t.assignee == agent.id and t.is_active]"),
        ('return "OVERDUE " + line if sla.is_breached(ticket, now) else line', "return line"),
    ],
    "T1": [("key = today.isoformat()", "key = now.date().isoformat()")],
    "T2": [("since <= (t.assigned_at or t.created_at) <= now", "since <= t.created_at <= now")],
}
# Partial builds that must fail at least one test of each listed id.
MUTANTS = {
    "cm1-only": ["H2", "H7", "H8", "H9"],   # first change handled, second change and follow-ups not
    "no-followups": ["H2", "H9"],          # both changes handled, follow-up questions never asked
}


def build(overlay, subs=()):
    tmp = Path(tempfile.mkdtemp(prefix="support-digest-"))
    shutil.copytree(HERE / "repo", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    if overlay:
        shutil.copytree(HERE / overlay, tmp, dirs_exist_ok=True)
    if subs:
        target = tmp / REF_DIGEST
        text = target.read_text()
        for old, new in subs:
            if text.count(old) != 1:
                raise SystemExit(f"mutant substitution matches {text.count(old)} times: {old!r}")
            text = text.replace(old, new)
        target.write_text(text)
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
    mutant_dirs = {}
    for name in MUTANTS:
        mutant_dirs[name] = build(f"mutants/{name}")
    missing = [i for i in ids if not i.startswith("E") and i not in ID_MUTANTS]
    if missing:
        problems.append(f"no one-item mutant for {missing}")
    id_dirs = {i: build("ref", subs) for i, subs in ID_MUTANTS.items()}
    try:
        mutant_results = {name: by_id(hidden_results(d)) for name, d in mutant_dirs.items()}
        id_results = {i: by_id(hidden_results(d)) for i, d in id_dirs.items()}
        ref_existing = run(ref, "tests").returncode == 0
        naive_existing = run(naive, "tests").returncode == 0
        r, n, b = by_id(hidden_results(ref)), by_id(hidden_results(naive)), by_id(hidden_results(bare))
    finally:
        for d in (ref, naive, bare, *mutant_dirs.values(), *id_dirs.values()):
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
    for name, must_fail in MUTANTS.items():
        res = mutant_results[name]
        passed = sorted(i for i in ids if res.get(i) and all(res[i]))
        missed = [i for i in must_fail if res.get(i) and all(res[i])]
        print(f"mutant {name}: passes {passed}; must fail {must_fail}: {'ok' if not missed else 'NO ' + str(missed)}")
        if missed:
            problems.append(f"mutant {name} passes {missed}")
    print("one-item mutants (each must fail its own id and nothing else):")
    for i, res in id_results.items():
        failing = [j for j in ids if res.get(j) and not all(res[j])]
        ok = failing == [i]
        print(f"  {i:<4} fails {failing}  {'ok' if ok else 'NO'}")
        if not ok:
            problems.append(f"mutant {i} fails {failing}")
    print(f"existing tests: ref {'pass' if ref_existing else 'FAIL'}, naive {'pass' if naive_existing else 'FAIL'}")
    if not (ref_existing and naive_existing):
        problems.append("existing tests")
    print("CLEAN" if not problems else f"PROBLEMS: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
