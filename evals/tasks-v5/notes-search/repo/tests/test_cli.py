import json

from conftest import SAMPLE


def test_new_and_show(jotter):
    out = jotter("new", "Garden plan", "--tag", "garden", "--stdin", stdin="Basil.\n")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith("garden-plan.md")
    shown = jotter("show", "garden plan", "--json")
    data = json.loads(shown.stdout)
    assert data["title"] == "Garden plan"
    assert data["tags"] == ["garden"]
    assert data["body"] == "Basil.\n"


def test_list_newest_first_and_tag_filter(jotter):
    jotter("new", "First", "--tag", "a")
    jotter("new", "Second", "--tag", "b")
    rows = json.loads(jotter("list", "--json").stdout)
    assert {r["title"] for r in rows} == {"First", "Second"}
    rows = json.loads(jotter("list", "--tag", "b", "--json").stdout)
    assert [r["title"] for r in rows] == ["Second"]


def test_list_hides_archived(jotter):
    jotter("new", "Keep")
    jotter("new", "Hide")
    assert jotter("archive", "hide").returncode == 0
    rows = json.loads(jotter("list", "--json").stdout)
    assert [r["title"] for r in rows] == ["Keep"]
    rows = json.loads(jotter("list", "--archived", "--json").stdout)
    assert len(rows) == 2


def test_tags_on_sample(jotter):
    out = jotter("tags", "--json", vault=SAMPLE)
    counts = json.loads(out.stdout)
    assert counts["work"] == 7
    assert counts["Work"] == 6


def test_tag_add_rm(jotter):
    jotter("new", "Thing")
    out = jotter("tag", "add", "thing", "x", "y")
    assert out.stdout.strip() == "thing.md: x, y"
    out = jotter("tag", "rm", "thing", "x")
    assert out.stdout.strip() == "thing.md: y"


def test_links_and_backlinks(jotter):
    jotter("new", "A", "--stdin", stdin="[[B]]\n")
    jotter("new", "B")
    assert jotter("links", "a").stdout.strip() == "B -> b.md"
    assert jotter("links", "b", "--back").stdout.strip() == "a.md"


def test_check_exit_code(jotter):
    jotter("new", "A", "--stdin", stdin="[[Missing]]\n")
    out = jotter("check")
    assert out.returncode == 1
    assert "broken link [[Missing]]" in out.stdout
