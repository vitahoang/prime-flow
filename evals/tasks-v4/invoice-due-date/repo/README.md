# invoicer

The invoicing tool for Hollis & Rye Studio. It reads our customers, invoices
and payments from JSON files and prints invoices, statements, reminder lists
and the overdue report.

    python -m invoicer list
    python -m invoicer show INV-1043          # add --html for the printable version
    python -m invoicer statement C002
    python -m invoicer reminders              # or: reminders --on 2026-10-08
    python -m invoicer overdue                # charges late fees, lists overdue invoices
    python -m invoicer reminders --send       # today's reminders, logged as sent

The daily run (every morning) is `overdue` followed by `reminders --send`.

## Data

The data directory (default `./data`, or `$INVOICER_DATA_DIR`) holds
`customers.json`, `invoices.json` and `payments.json`, plus two logs the
daily run appends to: `fees.json` (late fees charged) and
`reminders_sent.json` (reminders sent). Each customer has an
IANA time zone and a billing currency. Timestamps in invoices.json are stored
in local time. Invoices from before 0.5 have only an `issued_on` date.

Set `INVOICER_NOW` (e.g. `2026-10-11T09:00:00Z`) to run as if it were that
moment, which is handy for month-end dry runs.

## Billing rules

- Payment terms are Net N days from the issue date (`terms` in the file).
- Reminders go out 7 days and 1 day before the due date.
- An invoice is overdue once its due day is over and money is still owed. The
  late fee is 2% of the balance, minimum 10.00 in the invoice currency. The
  `overdue` run charges it once per invoice and records it in fees.json.

## Layout

- `invoicer/cli.py`: commands
- `invoicer/store.py`: loading the JSON files
- `invoicer/models.py`: customers, invoices, payments
- `invoicer/dates.py`: terms, due dates, aging
- `invoicer/billing.py`: balances, overdue status, late fees
- `invoicer/reminders.py`: reminder schedule
- `invoicer/render.py`: text and HTML invoices
- `invoicer/statement.py`: customer statements
- `invoicer/money.py`, `invoicer/utils.py`: formatting helpers

## Tests

    python -m pytest
