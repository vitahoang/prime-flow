import pytest

from tickoff.clock import ManualWall
from tickoff.replica import Replica


@pytest.fixture
def wall():
    return ManualWall("2026-10-20T09:00:00Z")


@pytest.fixture
def replica(wall):
    return Replica("laptop", wall=wall)


@pytest.fixture
def errands(replica, wall):
    """A list with three tasks: stamps, bank, post office."""
    ids = []
    for title in ("Buy stamps", "Call the bank", "Post the parcel"):
        ids.append(replica.add_task(title, list="errands").id)
        wall.advance(30)
    return ids


def titles(replica, list_name="inbox"):
    return [t.title for t in replica.list_tasks(list_name)]
