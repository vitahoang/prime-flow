"""One-off import from an Evernote export (.enex).

Used in 2021 to bring the old Evernote notebooks across. Evernote tags and
notebook names come over as they were spelled there (`Work`, `Travel`...),
and each imported note gets `source: evernote`.
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from jotter import dates
from jotter.note import Note

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(div|p|br|li|h[1-6]|tr)[^>]*>", re.I)


def enml_to_markdown(enml):
    """Very rough ENML -> Markdown: block tags become newlines, the rest is dropped."""
    text = re.sub(r"<li[^>]*>", "\n- ", enml, flags=re.I)
    text = _BLOCK.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    out, blank = [], False
    for line in lines:
        if not line.strip():
            if not blank and out:
                out.append("")
            blank = True
            continue
        out.append(line.strip())
        blank = False
    return "\n".join(out).strip() + "\n"


def _enex_time(value):
    if not value:
        return None
    return datetime.strptime(value.strip(), "%Y%m%dT%H%M%SZ")


def read_enex(path, notebook=None):
    """Yield (title, tags, created, updated, markdown) for each note in the file."""
    tree = ET.parse(path)
    for el in tree.getroot().iter("note"):
        title = (el.findtext("title") or "Untitled").strip()
        tags = [t.text.strip() for t in el.findall("tag") if t.text and t.text.strip()]
        if notebook and notebook not in tags:
            tags.insert(0, notebook)
        created = _enex_time(el.findtext("created"))
        updated = _enex_time(el.findtext("updated")) or created
        body = enml_to_markdown(el.findtext("content") or "")
        yield title, tags, created, updated, body


def import_enex(store, path, notebook=None, dry_run=False):
    """Create one note per Evernote note. Returns the new notes."""
    created_notes = []
    for title, tags, created, updated, body in read_enex(path, notebook):
        meta = {"title": title, "tags": tags}
        if created:
            meta["created"] = dates.format(created)
        if updated:
            meta["updated"] = dates.format(updated)
        meta["source"] = "evernote"
        note = Note(store.path_for(title), meta, body)
        if not dry_run:
            store.save(note, touch=False)
        created_notes.append(note)
    return created_notes
