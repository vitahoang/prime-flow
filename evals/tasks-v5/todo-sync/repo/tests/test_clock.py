from tickoff.clock import LamportClock, ManualWall, SystemWall, parse_wall, today


def test_lamport_tick_and_observe():
    c = LamportClock()
    assert c.tick() == 1
    assert c.tick() == 2
    assert c.observe(10) == 10
    assert c.observe(3) == 10
    assert c.tick() == 11


def test_manual_wall():
    w = ManualWall("2026-10-20T09:00:00Z")
    assert w.now() == "2026-10-20T09:00:00Z"
    assert w.advance(90) == "2026-10-20T09:01:30Z"
    w.set("2026-12-31T23:59:59Z")
    assert today(w) == "2026-12-31"


def test_system_wall_format_and_skew():
    plain = parse_wall(SystemWall().now())
    behind = parse_wall(SystemWall(skew_seconds=-7200).now())
    assert 7190 <= (plain - behind).total_seconds() <= 7210
