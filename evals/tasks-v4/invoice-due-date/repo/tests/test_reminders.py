from datetime import date

from invoicer import reminders
from invoicer.store import Store

from .conftest import utc

NOW = utc(2026, 9, 15, 12, 0)


def test_upcoming_from_today(store):
    items = reminders.upcoming(store, NOW)
    assert [(r.send_on, r.invoice_id, r.days_before) for r in items] == [
        (date(2026, 9, 17), "INV-2", 1),
        (date(2026, 9, 24), "INV-1", 7),
        (date(2026, 9, 25), "INV-3", 7),
        (date(2026, 9, 30), "INV-1", 1),
        (date(2026, 10, 1), "INV-3", 1),
    ]


def test_paid_and_void_get_no_reminders(store):
    ids = {r.invoice_id for r in reminders.upcoming(store, NOW)}
    assert "INV-4" not in ids and "INV-5" not in ids


def test_filter_by_day(store):
    items = reminders.upcoming(store, NOW, on=date(2026, 9, 24))
    assert [r.invoice_id for r in items] == ["INV-1"]


def test_past_reminders_are_not_listed(store):
    items = reminders.upcoming(store, utc(2026, 9, 26, 12, 0))
    assert all(r.send_on >= date(2026, 9, 26) for r in items)


def test_format_reminder(store):
    r = reminders.upcoming(store, NOW, on=date(2026, 9, 24))[0]
    assert reminders.format_reminder(r) == "2026-09-24  INV-1  Northgate Books  7 days before due (2026-10-01)"


def test_reminder_email_mentions_due_date(store):
    r = reminders.upcoming(store, NOW, on=date(2026, 9, 24))[0]
    body = reminders.reminder_email(r)
    assert "INV-1" in body and "1 Oct 2026" in body


def test_sent_reminders_are_not_listed_again(store):
    store.log_sent("INV-1", date(2026, 9, 24))
    pairs = {(r.invoice_id, r.days_before) for r in reminders.upcoming(store, NOW)}
    assert ("INV-1", 7) not in pairs
    assert ("INV-1", 1) in pairs


def test_send_due_records_todays_reminders(store, data_dir):
    sent = reminders.send_due(store, utc(2026, 9, 24, 9))
    assert [r.invoice_id for r in sent] == ["INV-1"]
    assert reminders.send_due(Store(data_dir), utc(2026, 9, 24, 15)) == []
