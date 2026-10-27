from folio import audit
from folio.textutil import plural, slugify, snippet, truncate


def test_events_recorded(world):
    s = world["store"]
    s.trash_document(world["doc"])
    actions = [e.action for e in audit.recent(s, resource_id=world["doc"])]
    assert actions == ["document.create", "document.trash"]
    assert "document.trash" in audit.format_event(s.events[-1])


def test_textutil():
    assert slugify("Harbour Library!") == "harbour-library"
    assert slugify("") == "untitled"
    assert truncate("a" * 50, 10).endswith("…")
    assert plural(1, "result") == "1 result" and plural(2, "result") == "2 results"
    assert "tide" in snippet("The tide line is higher", "tide")
