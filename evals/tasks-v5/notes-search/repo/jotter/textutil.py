"""Small text helpers shared by the store, the CLI and the importer."""

import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"\w+", re.UNICODE)
_MD_NOISE = re.compile(r"(`{1,3}|\*\*|__|[*_~>]|^#+\s*|!\[[^\]]*\]\([^)]*\))", re.M)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _ascii(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def slugify(title, max_len=60):
    """File name stem for a title: 'Garden plan (2026)' -> 'garden-plan-2026'."""
    slug = _NON_SLUG.sub("-", _ascii(title).lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rsplit("-", 1)[0] or slug[:max_len]
    return slug or "untitled"


def words(text):
    return _WORD.findall(text)


def word_count(text):
    return len(words(text))


def strip_markdown(text):
    """Rough plain text for excerpts: drops emphasis, headings, images, link URLs."""
    text = _LINK.sub(r"\1", text)
    text = _MD_NOISE.sub("", text)
    return text


def excerpt(body, limit=80):
    """First non-empty line of plain text, cut at a word boundary."""
    for line in strip_markdown(body).splitlines():
        line = " ".join(line.split())
        if line:
            if len(line) <= limit:
                return line
            cut = line[:limit].rsplit(" ", 1)[0]
            return cut + "…"
    return ""


def normalize_ws(text):
    return re.sub(r"[ \t]+\n", "\n", text).rstrip() + "\n"
