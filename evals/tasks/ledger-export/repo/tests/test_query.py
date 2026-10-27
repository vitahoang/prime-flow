from ledger import query
from ledger.models import Entry

E = [
    Entry(1, "2026-01-31T23:00:00Z", "a", 100),
    Entry(2, "2026-02-01T00:00:00Z", "b", 200, archived=True),
    Entry(3, "2026-02-15T12:00:00Z", "c", -50, "food"),
]


def test_in_range_half_open():
    start = query.parse_date("2026-02-01")
    end = query.parse_date("2026-02-15")
    assert [e.id for e in query.in_range(E, start, end)] == [2]


def test_in_range_open_bounds():
    assert len(query.in_range(E)) == 3


def test_active_and_total():
    assert query.total_cents(query.active(E)) == 50


def test_by_category():
    assert [e.id for e in query.by_category(E, "food")] == [3]
