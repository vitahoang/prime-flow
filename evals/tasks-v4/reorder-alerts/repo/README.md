# stockroom

Stock for the three Crumb & Co shops: Harbour (`HAR`), Market Street (`MKT`) and
Station Road (`STN`). Every shop sells coffee and bakes on site, so most of what
we track is milk, dough, beans and packaging.

    python -m stockroom stock                  # chain-wide stock on hand
    python -m stockroom stock --shop MKT       # one shop
    python -m stockroom stock --by-shop --activity
    python -m stockroom movements --shop HAR --days 14
    python -m stockroom po list --status open
    python -m stockroom check                  # sanity-check the data

Most commands take `--json`. The data directory is `--data DIR`, else
`$STOCKROOM_DATA`, else `./data`. Set `STOCKROOM_TODAY=YYYY-MM-DD` to run as if
it were another day.

## Data

| File | What |
|---|---|
| `shops.json` | shop code and name |
| `items.json` | one row per SKU: name, unit, supplier, category, `min_stock` |
| `suppliers.json` | supplier, `lead_time_days`, and per SKU the `case_size` and `unit_cost` |
| `movements.csv` | every stock movement; the POS appends sales nightly |
| `purchase_orders.json` | POs with status `open`, `received` or `cancelled` |

Movement types: `sale`, `delivery`, `waste`, `transfer_in` / `transfer_out`
(between our own shops, matched by `ref`) and `return` (sent back to a
supplier). `qty` is always positive; the type gives the direction. When a PO
arrives, the delivery is recorded in `movements.csv` and the PO is marked
`received`.

Item fields:

- `unit` — what we count in (carton, sheet, bag...)
- `supplier` — id in `suppliers.json`
- `min_stock` — chain-wide minimum, used for reorder warnings (planned)

`data/` holds demo data; regenerate it with `python tools/make_demo_data.py`.

## Layout

- `stockroom/models.py` — records and the `MovementType` / `POStatus` enums
- `stockroom/store.py` — loading and saving the data directory
- `stockroom/ledger.py` — stock on hand and movement filters
- `stockroom/purchasing.py` — purchase order helpers
- `stockroom/validation.py` — `check`
- `stockroom/formatting.py`, `stockroom/units.py` — output
- `stockroom/legacy_import.py` — the one-off import from the old stock sheet
- `stockroom/cli.py` — commands

## Tests

    python -m pytest
