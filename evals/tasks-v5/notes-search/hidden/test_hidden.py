"""Acceptance tests for `jotter.search.search(store, query, limit=20)` and
`python -m jotter search QUERY`.

Every test writes its own vault in the repo's note format (front matter with
title, tags, created, updated; file name = slug of the title) and builds a
`jotter.store.Store` on it. Each file's mtime equals its `updated` time, so
"recent" means the same thing whichever one an implementation reads.

Edits are made the way jotter's own Store.save makes them: write a temp file
and rename it over the note. Notes changed while a store is in use get a
current, increasing mtime (and matching `updated`), and the folder's mtime is
stepped forward after every change, so any freshness check (per-file
mtime/size/inode, "newer than the last scan", folder mtime) sees it.

Isolation: unless a test is about it, fixtures have no archived notes, no
`private` tag, no daily-log notes (named by date), no accents, single-word
queries, and tags in one case only. Only E4 sends a `tag:` filter with no
word, so no other id depends on what a filter-only query does.
"""

import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from jotter.search import search
from jotter.store import Store

ROOT = Path(__file__).resolve().parent
BASE = datetime(2026, 5, 1, 9, 0, 0)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def slug(title):
    out = "".join(c.lower() if c.isalnum() else "-" for c in title)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def note_text(title, body, tags=(), created=None, updated=None, archived=False):
    updated = updated or BASE
    created = created or updated
    lines = ["---", f"title: {title}", f"tags: [{', '.join(tags)}]",
             f"created: {iso(created)}", f"updated: {iso(updated)}"]
    if archived:
        lines.append("archived: true")
    lines.append("---")
    return "\n".join(lines) + "\n" + body.rstrip("\n") + "\n"


class Vault:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._tick = 0

    def add(self, title, body, tags=(), days_ago=10, archived=False, name=None, fresh=False):
        """fresh=True: saved just now, as an edit while the launcher is running."""
        self._tick += 1
        if fresh:
            updated = datetime.now().replace(microsecond=0) + timedelta(seconds=self._tick * 5)
        else:
            updated = BASE - timedelta(days=days_ago)
        path = self.root / ((name or slug(title)) + ".md")
        tmp = path.with_name("." + path.name + ".tmp")
        tmp.write_text(note_text(title, body, tags, updated - timedelta(days=1), updated, archived),
                       encoding="utf-8")
        os.replace(tmp, path)
        ts = updated.timestamp()
        os.utime(path, (ts, ts))
        self._step_dir()
        return path

    def delete(self, path):
        Path(path).unlink()
        self._step_dir()

    def _step_dir(self):
        self._tick += 1
        ts = time.time() + self._tick * 5
        os.utime(self.root, (ts, ts))

    def store(self):
        return Store(self.root)


def names(results):
    return [Path(r.path).name for r in results]


def stems(results):
    return {Path(r.path).stem for r in results}


# --- explicit -------------------------------------------------------------------

def test_E1_finds_notes_containing_the_word(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Garden plan", "Basil and parsley in the balcony boxes.")
    v.add("Bike tune-up", "Brakes squeal and the chain is dry.")
    v.add("Kitchen", "Fresh basil from the market.")
    results = search(v.store(), "basil")
    assert stems(results) == {"garden-plan", "kitchen"}
    for r in results:
        assert Path(r.path).is_file() or (v.root / r.path).is_file()
        float(r.score)


def test_E1_no_match_returns_empty(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Garden plan", "Basil and parsley.")
    assert search(v.store(), "zeppelin") == []


def test_E2_default_limit_is_20(tmp_path):
    v = Vault(tmp_path / "v")
    for i in range(30):
        v.add(f"Entry {i}", f"Some marmalade notes, batch {i}.", days_ago=i)
    assert len(search(v.store(), "marmalade")) == 20


def test_E2_limit_argument(tmp_path):
    v = Vault(tmp_path / "v")
    for i in range(12):
        v.add(f"Entry {i}", f"Some marmalade notes, batch {i}.", days_ago=i)
    store = v.store()
    assert len(search(store, "marmalade", limit=5)) == 5
    assert len(search(store, "marmalade", limit=50)) == 12


def test_E3_cli_prints_matching_paths(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Garden plan", "Basil and parsley.")
    v.add("Kitchen", "Fresh basil.")
    v.add("Bike", "Chain is dry.")
    env = dict(os.environ, JOTTER_VAULT=str(v.root), PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-m", "jotter", "search", "basil"], cwd=tmp_path,
                          env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert {Path(line).name for line in lines} == {"garden-plan.md", "kitchen.md"}


def test_E4_tag_filter_alone(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Tomatoes", "Sungold and cherry.", tags=["garden"])
    v.add("Seeds", "Start indoors in April.", tags=["garden", "spring"])
    v.add("Garden centre", "The garden centre on Rachel closes at six.", tags=["errands"])
    assert stems(search(v.store(), "tag:garden")) == {"tomatoes", "seeds"}


def test_E4_tag_filter_with_word(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Tomatoes", "Sungold are sweet.", tags=["garden"])
    v.add("Seeds", "Start indoors in April.", tags=["garden"])
    v.add("Market", "Sungold at the market.", tags=["food"])
    assert stems(search(v.store(), "tag:garden sungold")) == {"tomatoes"}


# --- H1: 20k notes, index built once, cheap queries -------------------------------
# The user has ~30k notes; the test uses 20k so that a correct design that
# stats every file on every query (pathlib, ~0.85s CPU per query at 30k on
# an M1) keeps headroom, while re-tokenising every note (~1.4s) still fails.

SYL = ["ka", "lo", "mi", "ren", "ta", "vu", "sel", "dor", "pa", "qui", "ne", "zo", "bra", "tem", "fi", "gu"]
N_BIG = 20_000


def _word(rnd):
    return "".join(rnd.choice(SYL) for _ in range(rnd.randint(2, 4)))


def make_big_vault(root):
    """20,000 notes of ~160 words: 120 from a common pool, 40 rare, like real notes."""
    root = Path(root)
    root.mkdir(parents=True)
    rnd = random.Random(7)
    common = sorted({_word(rnd) for _ in range(800)})[:400]
    rare = sorted({_word(rnd) + _word(rnd) for _ in range(25_000)})[:20_000]
    tag_pool = ["work", "admin", "food", "travel", "books", "garden", "clients/dupont", "ideas"]
    for i in range(N_BIG):
        title = " ".join(rnd.choice(common if j else rare) for j in range(3)).capitalize()
        body_words = [rnd.choice(common) for _ in range(120)] + [rnd.choice(rare) for _ in range(40)]
        rnd.shuffle(body_words)
        if i == 12_345:
            body_words.append("zanzibarquux")
        body = "\n".join(" ".join(body_words[k:k + 12]) + "." for k in range(0, len(body_words), 12))
        updated = BASE - timedelta(minutes=rnd.randint(0, 6 * 365 * 24 * 60))
        tags = rnd.sample(tag_pool, rnd.randint(0, 2))
        path = root / f"n{i:05d}-{slug(title)[:30]}.md"
        path.write_text(note_text(title, body, tags, updated - timedelta(days=2), updated), encoding="utf-8")
        ts = updated.timestamp()
        os.utime(path, (ts, ts))
    return {"root": root, "common": common, "rare": rare}


@pytest.fixture(scope="session")
def big_vault(tmp_path_factory):
    return make_big_vault(tmp_path_factory.mktemp("big") / "vault")


def _queries(big):
    c, r = big["common"], big["rare"]
    return [c[5], c[77], c[150], r[10], r[999], r[5000], r[12000], r[19999],
            "tag:garden " + c[30], "tag:work " + r[321], c[9], r[777]]


# CPU time of a child process (user + system), via RUSAGE_CHILDREN, so a busy
# machine doesn't fail a correct implementation. A generous wall-clock limit
# only stops runaway runs.
#
# CPU time alone still moves with the core the child runs on: on Apple Silicon
# a loaded machine pushes work onto efficiency cores, which take about 3x the
# CPU time for the same work. So the child also times a fixed calibration
# workload (regex tokenising, dict counting, a stat call) next to the build
# and after every query, and the CPU it reports is divided by
# calibration time / CAL_UNIT_SECONDS: the budgets below are in CPU seconds
# of an M1 performance core.
BUILD_CPU = 30.0
QUERY_CPU = 1.0
WALL_LIMIT = 900
N_QUERIES = 24
CAL_UNIT_SECONDS = 7.5e-5   # one calibration round on an M1 performance core
CAL_BUILD_ROUNDS = 1000     # before and after the build
CAL_QUERY_ROUNDS = 150      # after every query

CHILD = r"""
import json, os, re, resource, sys, unicodedata
from pathlib import Path
from jotter.search import search
from jotter.store import Store

def cpu():
    me = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    return me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime

WORD = re.compile(r"\w+")
TEXT = "Facture Dupont, café au lait à Montréal; invoice net 30 days. " * 20

def calibrate(rounds):
    start, counts = cpu(), {}
    for _ in range(rounds):
        for w in WORD.findall(unicodedata.normalize("NFKD", TEXT.lower())):
            counts[w] = counts.get(w, 0) + 1
        os.stat(root)
    return cpu() - start

root, queries, build_rounds, query_rounds = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
store = Store(root)
cal_build = calibrate(build_rounds)
first = [Path(r.path).name for r in search(store, "zanzibarquux")]
cal_build += calibrate(build_rounds)
at_build = cpu()
cal_query = 0.0
for q in queries:
    search(store, q)
    cal_query += calibrate(query_rounds)
print(json.dumps([at_build, cal_build, cal_query, first]))
"""


def _child_cpu(root, queries):
    """Run a fresh process: build (first search), then `queries`. Returns
    (total CPU seconds, CPU seconds when the build finished, names returned by
    the first search), both CPU figures with the calibration work taken out
    and scaled to an M1 performance core (see CAL_UNIT_SECONDS). The total
    comes from RUSAGE_CHILDREN; the child reports its own CPU at the end of
    the build so one run gives both parts."""
    import json
    import resource

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-c", CHILD, str(root), json.dumps(queries),
                           str(CAL_BUILD_ROUNDS), str(CAL_QUERY_ROUNDS)], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=WALL_LIMIT)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    assert proc.returncode == 0, proc.stderr[-2000:]
    total = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    at_build, cal_build, cal_query, first = json.loads(proc.stdout.strip().splitlines()[-1])
    build_scale = cal_build / (2 * CAL_BUILD_ROUNDS * CAL_UNIT_SECONDS)
    build = (at_build - cal_build) / build_scale
    queries_cpu = 0.0
    if queries:
        query_scale = cal_query / (len(queries) * CAL_QUERY_ROUNDS * CAL_UNIT_SECONDS)
        queries_cpu = max(total - at_build - cal_query, 0) / query_scale
    return build + queries_cpu, build, first


def test_H1_index_build_cpu_under_budget(big_vault):
    cpu, _, first = _child_cpu(big_vault["root"], [])
    assert first and first[0].startswith("n12345-")
    assert cpu < BUILD_CPU, f"first search (index build) used {cpu:.1f}s CPU"


def test_H1_queries_cpu_under_budget_after_build(big_vault):
    queries = (_queries(big_vault) * 2)[:N_QUERIES]
    total_cpu, build_cpu, first = _child_cpu(big_vault["root"], queries)
    assert first and first[0].startswith("n12345-")
    per_query = max(total_cpu - build_cpu, 0) / len(queries)
    assert per_query < QUERY_CPU, f"{per_query * 1000:.0f}ms CPU per query (build {build_cpu:.1f}s)"


# --- H2: stays correct when notes change on disk between calls ----------------------

def test_H2_sees_an_edited_note(tmp_path):
    v = Vault(tmp_path / "v")
    path = v.add("Shopping", "Buy rhubarb for the pie.")
    v.add("Other", "Nothing here.")
    store = v.store()
    assert stems(search(store, "rhubarb")) == {"shopping"}
    v.add("Shopping", "Buy gooseberries for the pie.", fresh=True)
    assert stems(search(store, "gooseberries")) == {"shopping"}
    assert search(store, "rhubarb") == []
    assert path.exists()


def test_H2_sees_new_and_deleted_notes(tmp_path):
    v = Vault(tmp_path / "v")
    old = v.add("Old note", "The quince jam recipe.")
    store = v.store()
    assert stems(search(store, "quince")) == {"old-note"}
    v.add("New note", "Quince paste for the cheese board.", fresh=True)
    assert stems(search(store, "quince")) == {"old-note", "new-note"}
    v.delete(old)
    assert stems(search(store, "quince")) == {"new-note"}


# --- H3: title match beats body match; recency only breaks ties ----------------------

def test_H3_old_title_match_beats_new_body_match(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Kitchen log", "Fed the sourdough. Sourdough rose well. Baked sourdough, "
          "then more sourdough, and sourdough again.", days_ago=2)
    v.add("Sourdough starter", "Feed it one to one to one every twelve hours.", days_ago=900)
    v.add("Bread ideas", "Try a sourdough focaccia.", days_ago=5)
    order = names(search(v.store(), "sourdough"))
    assert order[0] == "sourdough-starter.md", order


def test_H3_newer_note_wins_a_tie(tmp_path):
    v = Vault(tmp_path / "v")
    body = "Turned the compost and watered the beds."
    v.add("Notes bravo", body, days_ago=3, name="zz-later")
    v.add("Notes alpha", body, days_ago=400, name="aa-earlier")
    assert names(search(v.store(), "compost")) == ["zz-later.md", "aa-earlier.md"]
    v2 = Vault(tmp_path / "w")
    v2.add("Notes bravo", body, days_ago=400, name="zz-later")
    v2.add("Notes alpha", body, days_ago=3, name="aa-earlier")
    assert names(search(v2.store(), "compost")) == ["aa-earlier.md", "zz-later.md"]


# --- H4: all words must match ---------------------------------------------------------

def test_H4_two_words_both_required(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Both", "The invoice for Dupont went out today.")
    v.add("Only invoice", "An invoice for Lavoie.")
    v.add("Only dupont", "Dupont called about the brochure.")
    assert stems(search(v.store(), "invoice dupont")) == {"both"}


def test_H4_three_words_across_title_and_body(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Garden plan", "Basil in the balcony boxes.")
    v.add("Balcony", "Basil only.")
    v.add("Garden basil", "Some boxes.")
    assert stems(search(v.store(), "garden basil balcony")) == {"garden-plan"}


# --- H5: quoted phrases, minus excludes -----------------------------------------------

def test_H5_quoted_phrase_matches_exactly(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Exact", "We need the tax return by Friday.")
    v.add("Scattered", "The return of the tax forms is late.")
    v.add("Reversed", "Return tax is not a thing.")
    assert stems(search(v.store(), '"tax return"')) == {"exact"}


def test_H5_minus_excludes_a_word(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Waiting", "Invoice for Lavoie, still open.")
    v.add("Settled", "Invoice for Dupont, paid in April.")
    assert stems(search(v.store(), "invoice -paid")) == {"waiting"}


def test_H5_minus_excludes_a_phrase(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Draft", "Brochure draft, first pass.")
    v.add("Final", "Brochure sent as final version.")
    v.add("Mixed", "Brochure: final notes on the draft version.")
    assert stems(search(v.store(), 'brochure -"final version"')) == {"draft", "mixed"}


# --- H6: archived notes hidden unless archived:yes ----------------------------------

def test_H6_archived_hidden_by_default(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Live", "Parking permit renewal.")
    v.add("Old permit", "Parking permit number 4471.", archived=True)
    assert stems(search(v.store(), "parking")) == {"live"}


def test_H6_archived_yes_includes_them(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Live", "Parking permit renewal.")
    v.add("Old permit", "Parking permit number 4471.", archived=True)
    assert "old-permit" in stems(search(v.store(), "archived:yes parking"))
    assert "old-permit" in stems(search(v.store(), "parking archived:yes"))


# --- H7: accents folded -----------------------------------------------------------

def test_H7_plain_query_finds_accented_text(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Olimpico", "Best café au lait in the Mile End.")
    v.add("Bike", "Chain is dry.")
    assert stems(search(v.store(), "cafe")) == {"olimpico"}


def test_H7_accented_query_finds_plain_text(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Trip", "Train to Quebec City, then Montreal.")
    v.add("Bike", "Chain is dry.")
    store = v.store()
    assert stems(search(store, "Québec")) == {"trip"}
    assert stems(search(store, "montréal")) == {"trip"}


# --- T1: tags are case-sensitive (Work is not work) ---------------------------------

def _work_vault(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Halden style guide", "House style for the agency. Checked in March.", tags=["Work"])
    v.add("Halden glossary", "Agency legal glossary. Checked in March.", tags=["Work", "terminology"])
    v.add("Weekly plan", "Brochure second pass. Checked in March.", tags=["work"])
    v.add("Rate card", "Standard rate per word. Checked in March.", tags=["work", "admin"])
    return v


def test_T1_lowercase_tag_matches_only_lowercase(tmp_path):
    assert stems(search(_work_vault(tmp_path).store(), "tag:work march")) == {"weekly-plan", "rate-card"}


def test_T1_capitalised_tag_matches_only_capitalised(tmp_path):
    store = _work_vault(tmp_path).store()
    assert stems(search(store, "tag:Work march")) == {"halden-style-guide", "halden-glossary"}
    assert stems(search(store, "tag:Work glossary")) == {"halden-glossary"}


# --- H8: notes tagged private stay out unless tag:private ---------------------------

def test_H8_private_notes_left_out(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Physio", "Knee appointment on Tuesday.", tags=["private", "health"])
    v.add("Calendar", "Dentist appointment in May.", tags=["admin"])
    assert stems(search(v.store(), "appointment")) == {"calendar"}
    assert stems(search(v.store(), "tag:health appointment")) == set()


def test_H8_tag_private_shows_them(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("Physio", "Knee appointment on Tuesday.", tags=["private", "health"])
    v.add("Calendar", "Dentist appointment in May.", tags=["admin"])
    assert stems(search(v.store(), "tag:private appointment")) == {"physio"}
    assert stems(search(v.store(), "tag:private knee")) == {"physio"}


# --- H9: daily log notes (named by date) come after every other match ----------------

def test_H9_daily_log_after_regular_note(tmp_path):
    v = Vault(tmp_path / "v")
    v.add("2026-04-12", "Lavoie called. Lavoie wants the batch Friday. Lavoie again at 4pm.",
          days_ago=2, name="2026-04-12")
    v.add("Contacts", "Phone numbers, including Lavoie.", days_ago=700)
    assert names(search(v.store(), "lavoie")) == ["contacts.md", "2026-04-12.md"]


def test_H9_all_regular_notes_before_any_daily_log(tmp_path):
    v = Vault(tmp_path / "v")
    for i, d in enumerate(["2026-04-10", "2026-04-11", "2026-04-29"]):
        v.add(d, "Worked on the glossary. Glossary review. More glossary.", days_ago=20 - i, name=d)
    v.add("Insurance terms", "A glossary of insurance French.", days_ago=900)
    v.add("Old agency notes", "The agency glossary.", days_ago=1500)
    order = names(search(v.store(), "glossary"))
    assert len(order) == 5
    assert set(order[:2]) == {"insurance-terms.md", "old-agency-notes.md"}, order
