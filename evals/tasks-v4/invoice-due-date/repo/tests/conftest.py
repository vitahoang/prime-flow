import json
from datetime import datetime, timezone

import pytest

from invoicer import cli
from invoicer.store import Store

CUSTOMERS = [
    {"id": "C1", "name": "Northgate Books", "email": "n@x", "timezone": "Europe/London", "currency": "GBP",
     "address": ["22 Northgate", "York"]},
    {"id": "C2", "name": "Lim & Tan Pte Ltd", "email": "l@x", "timezone": "Asia/Singapore", "currency": "SGD"},
    {"id": "C3", "name": "Brightline Media", "email": "b@x", "timezone": "America/Los_Angeles", "currency": "USD"},
]

INVOICES = [
    {"id": "INV-1", "customer": "C1", "issued_at": "2026-09-01T10:00:00Z", "terms": "Net 30", "currency": "GBP",
     "lines": [{"description": "Catalogue design", "quantity": 1, "unit_price": "1000.00"}], "tax_rate": "0.20"},
    {"id": "INV-2", "customer": "C2", "issued_at": "2026-09-03T02:00:00Z", "terms": "Net 15", "currency": "SGD",
     "lines": [{"description": "Annual report", "quantity": 2, "unit_price": "1500.00"}]},
    {"id": "INV-3", "customer": "C3", "issued_at": "2026-09-02T17:00:00Z", "terms": "Net 30", "currency": "USD",
     "lines": [{"description": "Podcast artwork", "quantity": 4, "unit_price": "250.00"}]},
    {"id": "INV-4", "customer": "C1", "issued_at": "2026-09-05T11:00:00Z", "terms": "Net 30", "currency": "GBP",
     "lines": [{"description": "Poster", "quantity": 1, "unit_price": "300.00"}]},
    {"id": "INV-5", "customer": "C1", "issued_at": "2026-09-06T11:00:00Z", "terms": "Net 30", "currency": "GBP",
     "lines": [{"description": "Cancelled job", "quantity": 1, "unit_price": "800.00"}], "void": True},
    {"id": "INV-0900", "customer": "C1", "issued_on": "2025-11-03", "terms": "Net 30", "currency": "GBP",
     "lines": [{"description": "Old job", "quantity": 1, "unit_price": "200.00"}]},
]

PAYMENTS = [
    {"invoice": "INV-4", "amount": "300.00", "paid_at": "2026-09-20T09:00:00Z"},
    {"invoice": "INV-3", "amount": "400.00", "paid_at": "2026-09-25T20:00:00Z", "method": "card"},
]

DEFAULT_NOW = "2026-09-15T12:00:00Z"


def write_data(root, customers=CUSTOMERS, invoices=INVOICES, payments=PAYMENTS):
    root.mkdir(parents=True, exist_ok=True)
    (root / "customers.json").write_text(json.dumps({"customers": customers}))
    (root / "invoices.json").write_text(json.dumps({"invoices": invoices}))
    (root / "payments.json").write_text(json.dumps({"payments": payments}))
    return root


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    root = write_data(tmp_path / "data")
    monkeypatch.setenv("INVOICER_DATA_DIR", str(root))
    monkeypatch.setenv("INVOICER_NOW", DEFAULT_NOW)
    return root


@pytest.fixture
def store(data_dir):
    return Store(data_dir)


@pytest.fixture
def run(data_dir, capsys, monkeypatch):
    def _run(*argv, now=None):
        if now:
            monkeypatch.setenv("INVOICER_NOW", now)
        code = cli.main(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err

    return _run


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)
