"""Payment reminder scheduling.

A reminder is due config.REMINDER_DAYS_BEFORE days before an invoice's due
date. The `reminders` command lists what is scheduled from today on;
`reminders --send` lists today's and records them in reminders_sent.json
(the mail-out itself is still done by hand from that list). A reminder that
is in the sent log is not listed again.
"""

from dataclasses import dataclass
from datetime import date, datetime

from . import billing, clock, config, dates, utils
from .models import Customer, Invoice


@dataclass(frozen=True)
class Reminder:
    send_on: date
    invoice_id: str
    customer_name: str
    customer_email: str
    days_before: int
    due: date


def already_sent(sent, invoice_id: str, send_on: date) -> bool:
    return (invoice_id, send_on) in sent


def schedule_for(invoice: Invoice, customer: Customer, payments, now: datetime, sent=()) -> list[Reminder]:
    """Reminders still to send for one invoice (none if paid or void)."""
    if billing.status(invoice, customer, payments, now) in (billing.PAID, billing.VOID):
        return []
    due = billing.due_date(invoice, customer)
    today = clock.local_today(customer.timezone, now)
    out = []
    for n in config.REMINDER_DAYS_BEFORE:
        send_on = dates.reminder_date(due, n)
        if send_on >= today and not already_sent(sent, invoice.id, send_on):
            out.append(Reminder(send_on, invoice.id, customer.name, customer.email, n, due))
    return out


def upcoming(store, now: datetime, on: date | None = None) -> list[Reminder]:
    out = []
    for inv in store.all_invoices():
        cust = store.customer_for(inv)
        out.extend(schedule_for(inv, cust, store.payments, now, store.sent_reminders))
    if on is not None:
        out = [r for r in out if r.send_on == on]
    return sorted(out, key=lambda r: (r.send_on, r.invoice_id, -r.days_before))


def send_due(store, now: datetime) -> list[Reminder]:
    """Today's reminders (in each customer's own calendar), recorded as sent."""
    out = []
    for inv in store.all_invoices():
        cust = store.customer_for(inv)
        today = clock.local_today(cust.timezone, now)
        for r in schedule_for(inv, cust, store.payments, now, store.sent_reminders):
            if r.send_on == today:
                store.log_sent(r.invoice_id, r.send_on)
                out.append(r)
    return out


def format_reminder(r: Reminder) -> str:
    when = utils.format_date(r.send_on, "iso")
    due = utils.format_date(r.due, "iso")
    return f"{when}  {r.invoice_id}  {r.customer_name}  {utils.plural(r.days_before, 'day')} before due ({due})"


def reminder_email(r: Reminder) -> str:
    """Body text for the reminder email (pasted into the mail client)."""
    due = utils.format_date(r.due)
    lead = "tomorrow" if r.days_before == 1 else f"in {r.days_before} days, on {due}"
    return (
        f"Hello {r.customer_name},\n\n"
        f"A friendly reminder that invoice {r.invoice_id} is due {lead}.\n"
        f"If you have already paid, thank you, and please ignore this note.\n\n"
        f"{config.BUSINESS_NAME}\n"
    )
