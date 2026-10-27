# helpdesk

The support desk library behind Acme Tools' customer support: tickets, agents,
assignment, SLA warnings and the emails that go to agents.

```python
from helpdesk.clock import SystemClock
from helpdesk.store import JsonStore
from helpdesk import workflow, assignment
from helpdesk.mailer import SmtpMailer

store, clock, mailer = JsonStore("store.json"), SystemClock(), SmtpMailer()
t = workflow.open_ticket(store, clock, "Can't log in", "customer@example.com")
assignment.auto_assign(store, clock, t.id, mailer=mailer)
```

## Layout

- `helpdesk/models.py`: `Ticket` (with its `events` trail), `Comment`, `Agent` (timezone, workdays, backup), `OutOfOffice`, statuses and priorities
- `helpdesk/workflow.py`: opening tickets, replies, status changes (keeps `updated_at` current)
- `helpdesk/assignment.py`: manual and automatic assignment, skipping agents who are away
- `helpdesk/notifications.py`: assignment emails and SLA warnings, de-duplicated via the store's notification log
- `helpdesk/templates.py`: email text
- `helpdesk/mailer.py`: `Mailer`, `FakeMailer` (records `.sent`), `SmtpMailer`
- `helpdesk/queues.py`: ticket queues (support, hardware, billing)
- `helpdesk/store.py`: `InMemoryStore` and `JsonStore`
- `helpdesk/sla.py`: response targets by priority
- `helpdesk/search.py`, `helpdesk/reports.py`: agent views and dashboard numbers
- `helpdesk/clock.py`: `SystemClock`, `FakeClock`; every time is aware UTC
- `helpdesk/jobs.py`: what cron runs every 15 minutes

## Statuses

`open` → `pending_customer` (we replied) ↔ `pending_agent` (the customer replied) → `resolved`.
A customer reply on a resolved ticket reopens it.

## Notes

- Agents' `timezone` is only used to show times in emails; all scheduling is in UTC.
- SLA targets are measured in business hours (see `sla.BUSINESS_HOURS_LEGACY`).

## Tests

    python -m pytest
