import json
from datetime import date

from tickoff import export
from tickoff.legacy_import import import_todotxt, parse_line


def test_markdown_roundtrip(replica, errands):
    replica.complete(errands[1])
    replica.set_due(errands[0], "2026-10-21")
    text = export.to_markdown(replica, date(2026, 10, 20))
    assert "## errands" in text
    assert "- [ ] Buy stamps (due tomorrow)" in text
    assert "- [x] Call the bank" in text
    assert export.from_markdown(text) == [
        ("errands", "Buy stamps", False), ("errands", "Call the bank", True), ("errands", "Post the parcel", False)]


def test_digest(replica, errands):
    data = json.loads(export.to_digest(replica))
    assert [t["title"] for t in data["errands"]] == ["Buy stamps", "Call the bank", "Post the parcel"]


def test_todotxt_line():
    assert parse_line("x 2025-03-02 Call the bank @errands due:2025-03-04") == {
        "title": "Call the bank", "done": True, "list": "errands", "due": "2025-03-04"}
    assert parse_line("# comment") is None


def test_todotxt_import(replica):
    n = import_todotxt(replica, "Buy stamps @errands\n(A) Finish report @work\nx Old thing\n")
    assert n == 3
    assert [t.title for t in replica.list_tasks("errands")] == ["Buy stamps"]
    assert replica.list_tasks("inbox")[0].done
