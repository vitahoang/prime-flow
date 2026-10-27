import json
from datetime import date, datetime

import pytest

from invoicer.store import DataError, Store

from .conftest import CUSTOMERS, INVOICES, utc, write_data


def test_loads_everything(store):
    assert len(store.customers) == 3
    assert len(store.invoices) == 6
    assert len(store.payments) == 2


def test_issued_at_is_aware_utc(store):
    inv = store.invoice("INV-1")
    assert isinstance(inv.issued, datetime)
    assert inv.issued == utc(2026, 9, 1, 10, 0)


def test_v0_record_keeps_plain_date(store):
    inv = store.invoice("INV-0900")
    assert inv.is_legacy
    assert inv.issued == date(2025, 11, 3)


def test_terms_parsed(store):
    assert store.invoice("INV-2").terms_days == 15


def test_lookup_is_case_insensitive_on_prefix(store):
    assert store.invoice("inv-1").id == "INV-1"


def test_totals(store):
    inv = store.invoice("INV-1")
    assert str(inv.subtotal) == "1000.00"
    assert str(inv.tax) == "200.00"
    assert str(inv.total) == "1200.00"


def test_unknown_customer_is_a_data_error(tmp_path):
    bad = [dict(INVOICES[0], customer="C99")]
    root = write_data(tmp_path / "d", invoices=bad)
    with pytest.raises(DataError):
        Store(root)


def test_invoice_without_issue_date_is_a_data_error(tmp_path):
    row = {k: v for k, v in INVOICES[0].items() if k != "issued_at"}
    root = write_data(tmp_path / "d", invoices=[row])
    with pytest.raises(DataError):
        Store(root)


def test_bad_json_is_a_data_error(tmp_path):
    root = write_data(tmp_path / "d")
    (root / "invoices.json").write_text("{nope")
    with pytest.raises(DataError):
        Store(root)


def test_missing_payments_file_is_fine(tmp_path):
    root = write_data(tmp_path / "d")
    (root / "payments.json").unlink()
    assert Store(root).payments == []


def test_customer_without_timezone_gets_business_zone(tmp_path):
    rows = [dict(CUSTOMERS[0])]
    del rows[0]["timezone"]
    root = write_data(tmp_path / "d", customers=rows, invoices=[INVOICES[0]], payments=[])
    assert Store(root).customer("C1").timezone == "Europe/London"


def test_loading_does_not_touch_files(data_dir):
    before = {p.name: p.read_bytes() for p in data_dir.iterdir()}
    Store(data_dir)
    assert before == {p.name: p.read_bytes() for p in data_dir.iterdir()}


def test_plain_list_file_also_loads(tmp_path):
    root = write_data(tmp_path / "d")
    (root / "customers.json").write_text(json.dumps(CUSTOMERS))
    assert len(Store(root).customers) == 3
