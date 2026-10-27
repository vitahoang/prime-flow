"""Export a replica as Markdown or as a JSON digest."""

from __future__ import annotations

import json
from datetime import date

from .due import describe


def to_markdown(replica, today: date | None = None, *, include_done: bool = True) -> str:
    lines = [f"# Tasks on {replica.device_id}", ""]
    for name in replica.lists():
        tasks = replica.list_tasks(name, include_done=include_done)
        if not tasks:
            continue
        lines.append(f"## {name}")
        lines.append("")
        for task in tasks:
            box = "x" if task.done else " "
            extra = ""
            if task.due:
                extra = f" (due {describe(task.due, today) if today else task.due})"
            lines.append(f"- [{box}] {task.title}{extra}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_digest(replica) -> str:
    """A compact JSON view: lists in order, tasks in order, no metadata."""
    out = {}
    for name in replica.lists():
        out[name] = [
            {"id": t.id, "title": t.title, "done": t.done, "due": t.due}
            for t in replica.list_tasks(name)
        ]
    return json.dumps(out, indent=2)


def from_markdown(text: str):
    """Parse the Markdown produced by to_markdown back into (list, title,
    done) triples. Due dates are not read back."""
    current = None
    out = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
        elif line.startswith("- [") and current and len(line) > 6:
            done = line[3] == "x"
            title = line[6:]
            if title.endswith(")") and " (due " in title:
                title = title[: title.rindex(" (due ")]
            out.append((current, title, done))
    return out
