import pytest

from folio import access
from folio.errors import AccessDenied


def test_owner_is_owner(world):
    s = world["store"]
    assert access.is_owner(s, world["olive"], world["doc"])
    assert access.is_owner(s, world["olive"], world["harbour"])
    assert not access.is_owner(s, world["marcus"], world["doc"])


def test_unknown_resource_is_not_owned(world):
    assert not access.is_owner(world["store"], world["olive"], "doc_9999")


def test_require_owner_raises(world):
    with pytest.raises(AccessDenied):
        access.require_owner(world["store"], world["marcus"], world["doc"])


def test_visible_documents_are_own_and_not_trashed(world):
    s = world["store"]
    other = s.create_document(world["harbour"], "Marcus notes", world["marcus"])
    assert [d.id for d in access.visible_documents(s, world["olive"])] == [world["doc"]]
    s.trash_document(world["doc"])
    assert access.visible_documents(s, world["olive"]) == []
    assert [d.id for d in access.trash_of(s, world["olive"])] == [world["doc"]]
    assert [d.id for d in access.visible_documents(s, world["marcus"])] == [other]
