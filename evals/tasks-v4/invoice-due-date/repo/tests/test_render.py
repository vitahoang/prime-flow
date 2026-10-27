from invoicer import render

from .conftest import utc

NOW = utc(2026, 9, 15, 12, 0)


def _text(store, invoice_id, now=NOW):
    inv = store.invoice(invoice_id)
    return render.render_text(inv, store.customer_for(inv), store.payments_for(inv.id), now)


def test_text_header_and_dates(store):
    out = _text(store, "INV-1")
    assert "INVOICE INV-1" in out
    assert "Bill to:  Northgate Books" in out
    assert "Issued:   1 Sep 2026" in out
    assert "Terms:    Net 30" in out
    assert "Due:      1 Oct 2026" in out
    assert "Status:   OPEN" in out


def test_text_totals_with_tax(store):
    out = _text(store, "INV-1")
    assert "Tax (20%)" in out
    assert "GBP 1,200.00" in out


def test_text_shows_part_payment(store):
    out = _text(store, "INV-3")
    assert "Paid" in out and "USD -400.00" in out
    assert "Amount due" in out and "USD 600.00" in out


def test_text_overdue_shows_late_fee(store):
    out = _text(store, "INV-1", now=utc(2026, 10, 5))
    assert "Status:   OVERDUE" in out
    assert "Late fee" in out and "GBP 24.00" in out


def test_singapore_daytime_invoice(store):
    out = _text(store, "INV-2")
    assert "Due:      18 Sep 2026" in out
    assert "SGD 3,000.00" in out


def test_html_has_due_and_status(store):
    inv = store.invoice("INV-1")
    html = render.render_html(inv, store.customer_for(inv), store.payments_for(inv.id), NOW)
    assert "<title>Invoice INV-1</title>" in html
    assert "<td class=due>1 Oct 2026</td>" in html
    assert "status-OPEN" in html


def test_html_escapes_names(store):
    inv = store.invoice("INV-2")
    html = render.render_html(inv, store.customer_for(inv), [], NOW)
    assert "Lim &amp; Tan Pte Ltd" in html
