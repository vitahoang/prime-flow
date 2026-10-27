"""Plain-text tables and number formatting for the CLI."""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence

from .units import plural


def fmt_qty(qty: float, unit: Optional[str] = None) -> str:
    if float(qty).is_integer():
        text = str(int(qty))
    else:
        text = f"{qty:.2f}".rstrip("0").rstrip(".")
    if unit:
        text = f"{text} {plural(unit, qty)}"
    return text


def fmt_money(value: float) -> str:
    return f"£{value:,.2f}"


def fmt_date(d: Optional[date]) -> str:
    return d.strftime("%a %d %b") if d else "-"


def table(headers: Sequence[str], rows: Sequence[Sequence[object]],
          align: Optional[str] = None) -> str:
    """Render rows as a fixed-width table.

    ``align`` is one character per column: ``l`` or ``r``. Numbers default to
    right-aligned, everything else to left.
    """
    cells: List[List[str]] = [[str(h) for h in headers]]
    for row in rows:
        cells.append(["" if c is None else str(c) for c in row])
    ncols = len(headers)
    if align is None:
        sample = rows[0] if rows else [""] * ncols
        align = "".join("r" if isinstance(v, (int, float)) else "l" for v in sample)
    widths = [max(len(r[i]) for r in cells) for i in range(ncols)]
    lines = []
    for n, row in enumerate(cells):
        parts = []
        for i, text in enumerate(row):
            parts.append(text.rjust(widths[i]) if align[i] == "r" else text.ljust(widths[i]))
        lines.append("  ".join(parts).rstrip())
        if n == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def heading(text: str) -> str:
    return f"{text}\n{'=' * len(text)}"
