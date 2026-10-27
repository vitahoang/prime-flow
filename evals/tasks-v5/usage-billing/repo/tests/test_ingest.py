from datetime import timedelta

import pytest

from meterly import ingest, store as store_mod
from meterly.models import parse_ts

NOW = parse_ts("2026-09-15T12:00:00Z")


def test_record_call(store, data_dir):
    e = ingest.record_call(store, "cus_harbour", now=NOW)
    assert e.units == 1 and e.source == "sdk" and e.received_at == NOW
    assert store_mod.load(data_dir).events[-1].event_id == e.event_id


def test_record_call_keeps_client_timestamp(store):
    ts = NOW - timedelta(hours=3)
    e = ingest.record_call(store, "cus_harbour", timestamp=ts, now=NOW, event_id="evt_given")
    assert e.timestamp == ts and e.event_id == "evt_given"


def test_record_batch(store):
    e = ingest.record_batch(store, "cus_pinecrest", 250, now=NOW)
    assert e.units == 250 and e.source == "batch"


def test_batch_needs_units(store):
    with pytest.raises(ingest.IngestError):
        ingest.record_batch(store, "cus_pinecrest", 0, now=NOW)


def test_rejects_unknown_customer(store):
    with pytest.raises(ingest.IngestError):
        ingest.record_call(store, "cus_nope", now=NOW)


def test_rejects_future_timestamp(store):
    with pytest.raises(ingest.IngestError):
        ingest.record_call(store, "cus_harbour", timestamp=NOW + timedelta(hours=1), now=NOW)


def test_handle_request_routes_batches(store):
    single = ingest.handle_request(store, "cus_harbour", {"event_id": "evt_1"}, now=NOW)
    batch = ingest.handle_request(store, "cus_harbour", {"event_id": "evt_2", "units": 40}, now=NOW)
    assert (single.source, single.units) == ("sdk", 1)
    assert (batch.source, batch.units) == ("batch", 40)


def test_retry_is_stored_again(store):
    ingest.handle_request(store, "cus_harbour", {"event_id": "evt_retry"}, now=NOW)
    ingest.handle_request(store, "cus_harbour", {"event_id": "evt_retry"}, now=NOW + timedelta(seconds=5))
    assert [e.event_id for e in store.events].count("evt_retry") == 2
