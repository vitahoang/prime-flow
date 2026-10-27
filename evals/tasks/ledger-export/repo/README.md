# ledger

A tiny command-line ledger for personal and small-business bookkeeping.

```
python -m ledger add 1250.00 "Invoice 104" --category income --when 2026-03-02
python -m ledger add -42.10 "Printer ink" --category office
python -m ledger list [--category office]
python -m ledger balance [--from 2026-03-01] [--to 2026-04-01]
python -m ledger archive 7 [--undo]
```

## Data

Everything lives in `$LEDGER_HOME` (default `~/.ledger`):

- `entries.json` — the entries. Timestamps are stored in UTC
  (`2026-03-02T15:00:00Z`); amounts are stored as integer cents
  (positive = income, negative = expense).
- `config.json` — optional settings, see `ledger/settings.py`:
  `timezone` (IANA name, default `America/Chicago`), `date_format`
  (strftime, default `%m/%d/%Y`) and `currency_symbol` (default `$`).

Archived entries stay in the file and in `list` (marked `[archived]`)
but are left out of `balance`.

## Development

```
python -m pytest
```
