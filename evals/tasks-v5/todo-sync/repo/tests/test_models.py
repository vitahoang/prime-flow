import pytest

from tickoff.models import Task, ValidationError, clean_list_name, clean_title, validate_fields


def test_clean_title_collapses_whitespace():
    assert clean_title("  Buy   stamps \n") == "Buy stamps"


def test_clean_title_rejects_empty_and_long():
    with pytest.raises(ValidationError):
        clean_title("   ")
    with pytest.raises(ValidationError):
        clean_title("x" * 201)


def test_list_names_are_lowercased():
    assert clean_list_name(" Errands ") == "errands"
    with pytest.raises(ValidationError):
        clean_list_name("a/b")


def test_validate_fields():
    assert validate_fields({"done": True, "due": "2026-11-01"}) == {"done": True, "due": "2026-11-01"}
    with pytest.raises(ValidationError):
        validate_fields({"due": "next tuesday"})
    with pytest.raises(ValidationError):
        validate_fields({"done": "yes"})
    with pytest.raises(ValidationError):
        validate_fields({"order": True})
    with pytest.raises(ValidationError):
        validate_fields({"colour": "red"})


def test_task_roundtrip_ignores_unknown_keys():
    t = Task(id="abc", title="x", due="2026-01-02")
    data = t.to_dict()
    data["extra"] = 1
    assert Task.from_dict(data) == t


def test_overdue():
    t = Task(id="a", title="x", due="2026-10-01")
    assert t.is_overdue("2026-10-02")
    assert not t.is_overdue("2026-10-01")
    t.done = True
    assert not t.is_overdue("2026-10-02")
