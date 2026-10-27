# Brief (private to the simulator)

I run a small bookkeeping business out of my home in Chicago: a handful of clients plus my own household accounts, all kept in this little `ledger` tool. Every month I send my accountant a spreadsheet of the month's entries, and right now I copy them out of `ledger list` by hand. I want a CSV export so I can do `python -m ledger export --format csv --from 2026-03-01 --to 2026-03-31 > march.csv`, open it, check it, and email it.

## What I need (answer like this if asked)

- **H1 — Excel on Windows.** My accountant (and I, on my office PC) open the file by double-clicking it in Excel on Windows. Last time someone sent me a plain UTF-8 CSV, every "é" turned into "Ã©" and the rows came out doubled-spaced on one machine. So the file needs to be UTF-8 *with a BOM* and Windows (CRLF) line endings — whatever makes Excel on Windows open it correctly with no import wizard. I have clients like "Café Lumière", so accents do matter.
- **H2 — My timezone, not UTC.** Entries are stored in UTC, but I think in Chicago time. If I paid for a dinner at 9:30pm on Feb 28, that's a February expense, and it must show as Feb 28 and land in February's export — not March 1. Use the timezone I've set in my ledger config (it's already there). The `--from`/`--to` dates mean dates on my calendar, in that same timezone.
- **H3 — No archived entries.** Archived entries are duplicates or voided things I've hidden. They must not be in the export by default; my accountant would count them. If you want to add a flag to include them, fine, but default is out.

## Decisions where the obvious choice is wrong for me

- **T1 — Amounts are plain numbers.** If you reuse the "$1,234.50" style from `list`, Excel treats it as text and my accountant can't sum the column. I want `1234.50` and `-45.00`: one amount column, minus sign for expenses, always two decimals, no currency symbol, no thousands separators.
- **T2 — `--to` is inclusive.** `--from 2026-03-01 --to 2026-03-31` means all of March, including everything on the 31st right up to midnight my time. I'd never type `--to 2026-04-01` to mean March.

## Things I don't care about ("your call")

- Exact column names and order, and whether there's an id or category column (I'd like the date, description and amount at least; category is nice).
- Date format in the date column: ISO `2026-03-31` or my usual `03/31/2026` are both fine. Showing the time too is fine.
- What happens with an unknown `--format` or a bad date — just give a sensible error.
- Whether `balance` also changes; I only asked for export.
- Sorting — oldest first is natural.

## If asked about things the code already tells you

I don't know the code by heart. If asked which timezone or date format I use, I'd say "whatever's in my config — I set it up once, Chicago I think". If asked how amounts are stored, "no idea, look at the code".
