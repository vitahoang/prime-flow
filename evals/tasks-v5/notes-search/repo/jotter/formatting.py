"""Plain-text and JSON output for the CLI."""

import json

from jotter import dates
from jotter.textutil import excerpt


def note_row(note, long=False):
    row = {
        "path": note.path.name,
        "title": note.title,
        "tags": note.tags,
        "updated": dates.short(note.updated),
    }
    if note.archived:
        row["archived"] = True
    if long:
        row["excerpt"] = excerpt(note.body)
    return row


def table(rows, columns):
    """Left-aligned columns, widths from the data."""
    if not rows:
        return ""
    widths = {c: max(len(c), *(len(_cell(r.get(c))) for r in rows)) for c in columns}
    lines = ["  ".join(c.upper().ljust(widths[c]) for c in columns).rstrip()]
    for r in rows:
        lines.append("  ".join(_cell(r.get(c)).ljust(widths[c]) for c in columns).rstrip())
    return "\n".join(lines)


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if value is True:
        return "yes"
    return str(value)


def notes_table(notes, long=False):
    rows = [note_row(n, long) for n in notes]
    columns = ["updated", "title", "tags"] + (["excerpt"] if long else [])
    return table(rows, columns)


def tag_counts(counts):
    if not counts:
        return ""
    width = max(len(t) for t in counts)
    return "\n".join(f"{tag.ljust(width)}  {n}" for tag, n in sorted(counts.items()))


def as_json(value):
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)
