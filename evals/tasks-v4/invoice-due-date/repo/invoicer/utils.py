"""Small formatting helpers shared by the renderers and the CLI."""

from datetime import date, datetime


def format_date(value, style: str = "long") -> str:
    """Format a date for people.

    long:  '4 Oct 2026'   (invoices, statements)
    short: '04/10/26'     (narrow table columns)
    iso:   '2026-10-04'   (machine-readable listings)
    """
    # FIXME: datetimes are cut down to their date here. Should this convert to
    # the customer's zone first? (Callers only pass dates at the moment.)
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise TypeError(f"format_date wants a date, got {type(value).__name__}")
    if style == "iso":
        return value.isoformat()
    if style == "short":
        return value.strftime("%d/%m/%y")
    return f"{value.day} {value.strftime('%b %Y')}"


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}{suffix}"


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "…"


def pad(text: str, width: int, align: str = "left") -> str:
    text = truncate(text, width)
    if align == "right":
        return text.rjust(width)
    return text.ljust(width)


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def table(rows, widths, aligns=None) -> list[str]:
    aligns = aligns or ["left"] * len(widths)
    out = []
    for row in rows:
        cells = [pad(str(c), w, a) for c, w, a in zip(row, widths, aligns)]
        out.append("  ".join(cells).rstrip())
    return out


def slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")
