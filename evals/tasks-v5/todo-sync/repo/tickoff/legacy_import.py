"""Import from the todo.txt files the old shell script kept.

Lines look like:

    x 2025-03-02 Call the bank @errands due:2025-03-04
    Buy stamps @errands
    (A) Finish the report @work due:2025-03-10

Kept for the two people still on the script; the CLI no longer exposes it.
"""

from __future__ import annotations

import re

LINE_RE = re.compile(r"^(?P<done>x\s+)?(?:\d{4}-\d{2}-\d{2}\s+)?(?:\([A-Z]\)\s+)?(?P<rest>.+)$")


def parse_line(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = LINE_RE.match(line)
    if not m:
        return None
    rest = m.group("rest")
    lists = re.findall(r"@(\w[\w-]*)", rest)
    due = re.search(r"\bdue:(\d{4}-\d{2}-\d{2})\b", rest)
    title = re.sub(r"\s*@\w[\w-]*|\s*\bdue:\S+", "", rest).strip()
    return {
        "title": title,
        "done": bool(m.group("done")),
        "list": lists[0].lower() if lists else "inbox",
        "due": due.group(1) if due else None,
    }


def import_todotxt(replica, text: str) -> int:
    count = 0
    for line in text.splitlines():
        item = parse_line(line)
        if not item or not item["title"]:
            continue
        task = replica.add_task(item["title"], list=item["list"], due=item["due"])
        if item["done"]:
            replica.complete(task.id)
        count += 1
    for name in replica.lists():
        replica.compact_orders(name)
    return count
