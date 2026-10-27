# meterly

Usage-based billing for the Geocodo address API. Customers pay a monthly base
fee for their plan plus a per-unit price for what they use.

## Layout

| Module | What it does |
|---|---|
| `models.py` | Customers, plans and tiers, plan history, usage events, the invoice draft model |
| `store.py` | Loads and saves the JSON data directory (`$METERLY_DATA`) |
| `money.py` | Decimal helpers, currency formatting |
| `pricing.py` | Plan price tables |
| `quote.py` | Estimates for the pricing page |
| `ingest.py` | What the usage endpoint calls for each SDK request |
| `usage.py` | Queries over usage events |
| `subscriptions.py` | Plan history and plan changes |
| `periods.py` | Billing periods (calendar months, end exclusive) and timezone helpers |
| `tax.py` | Tax rates by customer country |
| `customers.py` | Customer admin and goodwill credit |
| `reports.py`, `export.py` | Support reports and CSV dumps |

## Data

The data directory holds `customers.json`, `plans.json`, `subscriptions.json`
and `events.jsonl`. See `examples/data/` for a small sample.

- Each usage event is one API call.
- Plan prices are in major units of the plan's currency, as strings.
- A customer pays in one currency and can only be on plans in that currency.
- Every customer has an IANA timezone; reports and exports use the customer's
  local days.

## Invoicing

Not built yet: month-end invoices still come out of the billing spreadsheet.
The `Invoice` model in `models.py` is a sketch.

## CLI

    python -m meterly --data examples/data customers
    python -m meterly --data examples/data plans
    python -m meterly --data examples/data quote 20000 --currency GBP
    python -m meterly --data examples/data activity --month 2026-09

## Tests

    python -m pytest
