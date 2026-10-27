import pytest

from jotter import frontmatter


def test_parse_basic():
    meta, body = frontmatter.parse("---\ntitle: Hello\ntags: [a, b]\narchived: true\n---\nBody\n")
    assert meta == {"title": "Hello", "tags": ["a", "b"], "archived": True}
    assert body == "Body\n"


def test_block_list():
    meta, _ = frontmatter.parse("---\ntags:\n  - one\n  - two\n---\n")
    assert meta["tags"] == ["one", "two"]


def test_no_front_matter():
    meta, body = frontmatter.parse("# Just text\n")
    assert meta == {}
    assert body == "# Just text\n"


def test_unclosed():
    with pytest.raises(frontmatter.FrontMatterError):
        frontmatter.parse("---\ntitle: x\n")


def test_quoted_and_ints():
    meta, _ = frontmatter.parse('---\ntitle: "yes: really"\ncount: 3\n---\n')
    assert meta == {"title": "yes: really", "count": 3}


def test_round_trip():
    meta = {"title": "Café: notes", "tags": ["a", "B"], "created": "2024-01-02T03:04:05", "archived": True}
    text = frontmatter.dump(meta, "Body line\n")
    again, body = frontmatter.parse(text)
    assert again == meta
    assert body == "Body line\n"


def test_empty_value_is_empty_string():
    meta, _ = frontmatter.parse("---\nsource:\ntags:\n---\n")
    assert meta == {"source": "", "tags": []}
