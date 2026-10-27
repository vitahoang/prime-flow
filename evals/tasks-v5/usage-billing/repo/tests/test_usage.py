from datetime import date

from meterly import usage
from meterly.models import parse_ts


def test_events_for_window(store):
    lo, hi = parse_ts("2026-09-01T00:00:00Z"), parse_ts("2026-09-02T00:00:00Z")
    ids = [e.event_id for e in usage.events_for(store, "cus_harbour", lo, hi)]
    assert ids == ["evt_a1f0c2d3e4b50001", "evt_a1f0c2d3e4b50002"]


def test_count_calls(store):
    lo, hi = parse_ts("2026-09-01T00:00:00Z"), parse_ts("2026-09-02T00:00:00Z")
    assert usage.count_calls(usage.events_for(store, "cus_harbour", lo, hi)) == 2


def test_daily_counts_uses_local_days(store):
    counts = usage.daily_counts(store.events_of("cus_sakura"), "Asia/Tokyo")
    assert counts == {date(2026, 9, 2): 1}


def test_last_seen(store):
    assert usage.last_seen(store, "cus_lindgren") == parse_ts("2026-09-03T07:45:12Z")
    assert usage.last_seen(store, "nobody") is None


def test_sources(store):
    assert usage.sources(store.events_of("cus_pinecrest")) == {"batch": 3}


def test_by_metric(store):
    assert set(usage.by_metric(store.events)) == {"api_calls"}


def test_busiest_hour(store):
    assert usage.busiest_hour(store.events_of("cus_pinecrest"), "UTC") == 15
    assert usage.busiest_hour([], "UTC") is None
