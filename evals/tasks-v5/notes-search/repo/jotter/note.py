"""One note: a Markdown file with front matter."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from jotter import dates, frontmatter, links, tags
from jotter.textutil import word_count

_H1 = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)


@dataclass
class Note:
    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""

    @classmethod
    def from_text(cls, path, text):
        meta, body = frontmatter.parse(text)
        return cls(Path(path), meta, body)

    @classmethod
    def read(cls, path):
        path = Path(path)
        return cls.from_text(path, path.read_text(encoding="utf-8"))

    def to_text(self):
        return frontmatter.dump(self.meta, self.body)

    # --- fields -------------------------------------------------------------

    @property
    def title(self):
        """Front-matter title, else the first '# heading', else the file name."""
        title = self.meta.get("title")
        if title:
            return str(title)
        m = _H1.search(self.body)
        if m:
            return m.group(1)
        return self.path.stem.replace("-", " ")

    @property
    def tags(self):
        front = self.meta.get("tags") or []
        if isinstance(front, str):
            front = [t for t in re.split(r"[,\s]+", front) if t]
        return tags.merge(front, tags.inline_tags(self.body))

    @property
    def created(self):
        return dates.parse(self.meta.get("created"))

    @property
    def updated(self):
        """Last edit time from front matter; falls back to `created`."""
        return dates.parse(self.meta.get("updated")) or self.created

    @property
    def archived(self):
        value = self.meta.get("archived", False)
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1")
        return bool(value)

    @property
    def aliases(self):
        value = self.meta.get("aliases") or []
        return [value] if isinstance(value, str) else list(value)

    @property
    def links(self):
        return links.extract(self.body)

    @property
    def words(self):
        return word_count(self.body)

    def has_tag(self, tag):
        """Exact match, or a parent of one of the note's tags."""
        tag = tags.clean(tag)
        return any(t == tag or t.startswith(tag + "/") for t in self.tags)

    def __repr__(self):
        return f"Note({self.path.name!r}, title={self.title!r})"
