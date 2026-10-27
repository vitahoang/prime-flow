from jotter import check

from conftest import write_note


def test_clean_vault(store):
    store.create("Fine", body="ok\n")
    assert check.problems(store) == []


def test_finds_problems(store):
    write_note(store.root, "a.md", "---\ntitle: Dup\ncreated: 2024-02-01\nupdated: 2024-01-01\n---\n[[Missing]]\n")
    write_note(store.root, "b.md", "---\ntitle: Dup\ncreated: 2024-01-01\ncolour: red\n---\n")
    write_note(store.root, "c.md", "---\ntitle: x\n")
    found = check.problems(store)
    messages = [m for _, m in found]
    assert "updated is before created" in messages
    assert "broken link [[Missing]]" in messages
    assert "unknown keys: colour" in messages
    assert any(m.startswith("bad front matter") for m in messages)
    assert sum(m.startswith("duplicate title") for m in messages) == 2


def test_sample_vault_is_clean(sample):
    assert check.problems(sample) == []
