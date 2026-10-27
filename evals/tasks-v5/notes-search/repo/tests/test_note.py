from pathlib import Path

from jotter.note import Note


def make(text, name="x.md"):
    return Note.from_text(Path(name), text)


def test_title_sources():
    assert make("---\ntitle: From meta\n---\n# Heading\n").title == "From meta"
    assert make("# Heading here\nbody").title == "Heading here"
    assert make("no title", "my-note.md").title == "my note"


def test_tags_merge_front_and_inline():
    n = make("---\ntags: [a, b]\n---\nSome #c and #a again, not `#code`.\n")
    assert n.tags == ["a", "b", "c"]


def test_inline_tags_skip_fenced_code():
    n = make("```\n#notatag\n```\n#real\n")
    assert n.tags == ["real"]


def test_dates_and_updated_fallback():
    n = make("---\ncreated: 2024-01-02\n---\n")
    assert n.created.year == 2024
    assert n.updated == n.created


def test_archived_flag():
    assert make("---\narchived: true\n---\n").archived
    assert make("---\narchived: \"yes\"\n---\n").archived
    assert not make("---\ntitle: x\n---\n").archived


def test_has_tag_parent():
    n = make("---\ntags: [clients/dupont]\n---\n")
    assert n.has_tag("clients")
    assert n.has_tag("clients/dupont")
    assert not n.has_tag("client")
