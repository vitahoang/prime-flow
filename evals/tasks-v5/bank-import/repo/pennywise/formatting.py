"""Turning records into text tables and JSON-ready dicts."""

import json

from .money import format_cents, to_decimal_str


def table(headers, rows, align=None):
    """Render a plain-text table. `align` is a string of 'l'/'r' per column."""
    rows = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    align = align or "l" * len(headers)

    def fmt(cells):
        out = []
        for i, cell in enumerate(cells):
            out.append(cell.rjust(widths[i]) if align[i] == "r" else cell.ljust(widths[i]))
        return "  ".join(out).rstrip()

    lines = [fmt(headers), fmt(["-" * w for w in widths])]
    lines.extend(fmt(row) for row in rows)
    return "\n".join(lines)


def transaction_dict(txn, account_name, category_names):
    return {
        "id": txn.id,
        "account": account_name,
        "date": txn.posted.isoformat(),
        "amount": to_decimal_str(txn.amount_cents),
        "amount_cents": txn.amount_cents,
        "description": txn.description,
        "category": category_names.get(txn.category_id),
        "source": txn.source,
    }


def transactions_table(txns, account_names, category_names, currency=None):
    rows = []
    for t in txns:
        rows.append([
            t.id,
            t.posted.isoformat(),
            account_names.get(t.account_id, "?"),
            format_cents(t.amount_cents, currency),
            category_names.get(t.category_id) or "-",
            t.description,
        ])
    return table(["id", "date", "account", "amount", "category", "description"], rows, "rllrll")


def dumps(data):
    return json.dumps(data, indent=2, ensure_ascii=False)


def truncate(text, width=40):
    return text if len(text) <= width else text[: width - 1] + "…"
