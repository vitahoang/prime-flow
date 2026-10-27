from taskmill.config import Config
from taskmill.supervisor import Supervisor


def test_one_slot_per_worker():
    sup = Supervisor(Config(workers=3))
    assert [s.index for s in sup.slots] == [0, 1, 2]
    assert all(s.process is None for s in sup.slots)


def test_stop_without_start_is_safe():
    Supervisor(Config(workers=2)).stop(timeout=0.1)
