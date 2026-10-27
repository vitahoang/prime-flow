import json

import pytest

from meterly import store as store_mod
from meterly.models import UsageEvent, parse_ts


def test_load_examples(store):
    assert set(store.customers) == {"cus_harbour", "cus_pinecrest", "cus_sakura", "cus_lindgren"}
    assert store.plan("pro_jpy").currency == "JPY"
    assert len(store.events) == 10


def test_data_dir_from_env(data_dir):
    st = store_mod.load()
    assert st.root == data_dir


def test_unknown_customer(store):
    with pytest.raises(store_mod.UnknownCustomer):
        store.customer("nope")


def test_append_event_persists(store, data_dir):
    ts = parse_ts("2026-09-10T10:00:00Z")
    store.append_event(UsageEvent("evt_x", "cus_harbour", ts, ts, 3))
    again = store_mod.load(data_dir)
    assert again.events[-1].event_id == "evt_x"
    assert again.events[-1].units == 3


def test_save_customers_round_trip(store, data_dir):
    store.customer("cus_harbour").name = "Harbour Ltd"
    store.save_customers()
    assert store_mod.load(data_dir).customer("cus_harbour").name == "Harbour Ltd"


def test_bad_event_line(data_dir):
    with (data_dir / "events.jsonl").open("a") as fh:
        fh.write(json.dumps({"customer_id": "cus_harbour"}) + "\n")
    with pytest.raises(store_mod.StoreError):
        store_mod.load(data_dir)


def test_missing_files_give_empty_store(tmp_path):
    st = store_mod.load(tmp_path / "empty")
    assert st.customers == {} and st.events == []
