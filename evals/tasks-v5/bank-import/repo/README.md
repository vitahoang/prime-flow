# pennywise

A small personal-finance ledger for the command line. Accounts, transactions,
categories with automatic rules, monthly reports and budgets, all in one
SQLite file.

```
python -m pennywise accounts add "Northbank" --bank northbank
python -m pennywise txn add --account Northbank --date 2025-08-04 --amount -4.50 --desc "Pret"
python -m pennywise rules add "PRET" --category "Eating out"
python -m pennywise rules apply
python -m pennywise report monthly 2025-08
```

The database is `--db PATH`, else `$PENNYWISE_DB`, else `~/.pennywise/pennywise.db`.

## Conventions

- Amounts are stored as integer cents. Money in is positive, money out is
  negative.
- Dates are stored as ISO `YYYY-MM-DD`. Every bank I use exports DD/MM/YYYY.
- Categories have a kind: `expense`, `income` or `transfer`. Transfers between
  my own accounts are left out of reports.

## Accounts and banks

Each account has a `bank`: `manual`, or one of the CSV profiles in
`pennywise/bank_profiles.py` (`northbank`, `kestrel`, `uscard`). Real exports
from each bank are in `samples/`.

## Roadmap

- **CSV import** (next): `pennywise import FILE --account NAME`, reading the
  bank's export with its profile. Exports overlap, so skip anything dated on
  or before the account's last entry (`Store.last_transaction_date`).
- Splitting a transaction across categories.
- Recurring transactions.

## Development

```
python -m pytest
```
