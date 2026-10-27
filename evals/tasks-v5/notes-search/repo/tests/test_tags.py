from pathlib import Path

from jotter import tags
from jotter.note import Note


def make(name, tag_list):
    return Note(Path(name), {"title": name, "tags": tag_list}, "")


def test_index_counts_and_parents():
    index = tags.TagIndex([make("a.md", ["clients/dupont"]), make("b.md", ["clients/lavoie", "work"])])
    counts = index.counts()
    assert counts["clients"] == 2
    assert counts["clients/dupont"] == 1
    assert index.paths("work") == {Path("b.md")}


def test_clean():
    assert tags.clean("#clients/dupont/ ") == "clients/dupont"


def test_add_remove():
    n = make("a.md", ["x"])
    assert tags.add_tag(n, "#y")
    assert not tags.add_tag(n, "y")
    assert n.meta["tags"] == ["x", "y"]
    assert tags.remove_tag(n, "x")
    assert n.meta["tags"] == ["y"]


def test_rename_tag(store):
    store.create("One", tags=["old"])
    store.create("Two", tags=["other"])
    changed = tags.rename_tag(store, "old", "new")
    assert [n.title for n in changed] == ["One"]
    assert store.get("one").tags == ["new"]
