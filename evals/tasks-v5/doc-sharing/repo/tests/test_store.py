import pytest

from folio.errors import Invalid, NotFound
from folio.models import ResourceKind, UserStatus
from folio.store import Store


def test_ids_carry_their_kind(world):
    s = world["store"]
    assert world["ws"].startswith("ws_")
    assert world["doc"].startswith("doc_")
    assert s.kind_of(world["harbour"]) is ResourceKind.FOLDER
    assert s.get(world["olive"]).name == "Olive"


def test_unknown_id_raises_not_found(world):
    with pytest.raises(NotFound):
        world["store"].get("doc_9999")
    with pytest.raises(NotFound):
        world["store"].get("nonsense")


def test_duplicate_email_rejected(world):
    with pytest.raises(Invalid):
        world["store"].add_user(world["ws"], "OLIVE@hollisgrey.com")


def test_bad_email_and_domain():
    s = Store()
    with pytest.raises(Invalid):
        s.add_workspace("X", domain="localhost")
    ws = s.add_workspace("X", domain="x.com")
    with pytest.raises(Invalid):
        s.add_user(ws, "no-at-sign")


def test_folder_names_unique_per_parent(world):
    s = world["store"]
    with pytest.raises(Invalid):
        s.create_folder(world["ws"], "Harbour", world["olive"], world["projects"])
    s.create_folder(world["ws"], "Harbour", world["olive"])  # top level is fine


def test_move_folder_into_itself_rejected(world):
    s = world["store"]
    with pytest.raises(Invalid):
        s.move_folder(world["projects"], world["harbour"])


def test_trash_and_restore(world):
    s = world["store"]
    s.trash_document(world["doc"])
    doc = s.get_document(world["doc"])
    assert doc.trashed and doc.trashed_at
    s.restore_document(world["doc"])
    assert not doc.trashed and doc.trashed_at is None


def test_suspend_and_reactivate(world):
    s = world["store"]
    s.suspend_user(world["marcus"])
    assert s.get_user(world["marcus"]).status is UserStatus.SUSPENDED
    s.reactivate_user(world["marcus"])
    assert s.get_user(world["marcus"]).active


def test_admins(world):
    s = world["store"]
    s.add_admin(world["ws"], world["olive"])
    assert s.get_workspace(world["ws"]).is_admin(world["olive"])
    s.remove_admin(world["ws"], world["olive"])
    assert not s.get_workspace(world["ws"]).is_admin(world["olive"])


def test_groups_and_subgroups(world):
    s = world["store"]
    studio = s.add_group(world["ws"], "Studio", [world["marcus"]])
    team = s.add_group(world["ws"], "Harbour team")
    s.add_subgroup(studio, team)
    s.add_member(team, world["olive"])
    assert s.get_group(studio).subgroups == [team]
    assert s.get_group(team).members == [world["olive"]]
    with pytest.raises(Invalid):
        s.add_subgroup(team, team)


def test_restricted_flag(world):
    s = world["store"]
    s.set_restricted(world["doc"])
    assert s.get_document(world["doc"]).restricted
    s.set_restricted(world["doc"], False)
    assert not s.get_document(world["doc"]).restricted
