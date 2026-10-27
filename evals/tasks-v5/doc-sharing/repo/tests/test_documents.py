import pytest

from folio import documents
from folio.errors import AccessDenied, Invalid


def test_owner_edits_and_history(world):
    s, olive, doc = world["store"], world["olive"], world["doc"]
    assert documents.edit(s, olive, doc, "v2") == 2
    assert documents.edit(s, olive, doc, "v2") == 2  # no-op edit
    assert [r.number for r in documents.history(s, olive, doc)] == [1, 2]
    assert documents.revert(s, olive, doc, 1) == 3
    assert documents.read(s, olive, doc) == "Reading room facing the water."


def test_non_owner_cannot_touch(world):
    s = world["store"]
    for fn, args in [(documents.read, ()), (documents.edit, ("x",)),
                     (documents.add_comment, ("hi",)), (documents.history, ())]:
        with pytest.raises(AccessDenied):
            fn(s, world["marcus"], world["doc"], *args)


def test_trashed_doc_cannot_be_read(world):
    s = world["store"]
    s.trash_document(world["doc"])
    with pytest.raises(Invalid):
        documents.read(s, world["olive"], world["doc"])


def test_comments(world):
    s, olive, doc = world["store"], world["olive"], world["doc"]
    c1 = documents.add_comment(s, olive, doc, "Check the tide line")
    c2 = documents.add_comment(s, olive, doc, "Ask about parking")
    documents.resolve_comment(s, olive, doc, c1)
    assert [c.id for c in documents.open_comments(s, olive, doc)] == [c2]
    with pytest.raises(Invalid):
        documents.add_comment(s, olive, doc, "   ")


def test_rename(world):
    s = world["store"]
    documents.rename(s, world["olive"], world["doc"], "Client brief")
    assert s.get_document(world["doc"]).title == "Client brief"
