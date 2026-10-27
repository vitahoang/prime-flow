import pytest

from tickoff import lists

from .conftest import titles


def test_rename_list_keeps_order(replica, errands):
    replica.add_task("Already here", list="town")
    assert lists.rename_list(replica, "errands", "town") == 3
    assert titles(replica, "town") == ["Already here", "Buy stamps", "Call the bank", "Post the parcel"]
    assert titles(replica, "errands") == []


def test_clear_done(replica, errands):
    replica.complete(errands[0])
    replica.complete(errands[2])
    assert lists.clear_done(replica, "errands") == 2
    assert titles(replica, "errands") == ["Call the bank"]


def test_archive(replica, errands):
    lists.archive_list(replica, "errands")
    assert len(titles(replica, "archive")) == 3
    with pytest.raises(ValueError):
        lists.archive_list(replica, "inbox")


def test_reverse(replica, errands):
    lists.reverse_list(replica, "errands")
    assert titles(replica, "errands") == ["Post the parcel", "Call the bank", "Buy stamps"]
