"""Read and write the front matter block at the top of a note.

A note starts with a block like:

    ---
    title: Sourdough starter
    tags: [baking, food]
    created: 2024-03-02T09:15:00
    updated: 2024-05-10T18:30:00
    ---

This is a deliberately small subset of YAML: `key: value` lines, inline lists
(`[a, b]`), block lists (`- a` on the following lines), quoted strings,
booleans and integers. Nested mappings are not supported; nobody has needed
them. Values are returned as str, bool, int or list[str]; dates stay strings
and are parsed by `jotter.dates`.
"""

import re

FENCE = "---"
_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}


class FrontMatterError(ValueError):
    pass


def split(text):
    """Return (front matter lines, body). No front matter -> ([], text)."""
    if not text.startswith(FENCE):
        return [], text
    lines = text.split("\n")
    if lines[0].strip() != FENCE:
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == FENCE:
            body = "\n".join(lines[i + 1:])
            return lines[1:i], body
    raise FrontMatterError("front matter is not closed with ---")


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _scalar(raw):
    value = raw.strip()
    if not value:
        return ""
    if value[0] in "'\"":
        return _unquote(value)
    low = value.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _inline_list(raw):
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [str(_scalar(part)) for part in inner.split(",") if part.strip()]


def parse(text):
    """Parse a note's text into (meta dict, body)."""
    lines, body = split(text)
    meta = {}
    key = None
    for lineno, line in enumerate(lines, start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") or stripped == "-":
            if key is None or not isinstance(meta.get(key), list):
                raise FrontMatterError(f"line {lineno}: list item outside a list")
            meta[key].append(str(_scalar(stripped[1:])))
            continue
        m = _KEY.match(line)
        if not m:
            raise FrontMatterError(f"line {lineno}: expected 'key: value', got {line!r}")
        key, raw = m.group(1), m.group(2)
        raw_s = raw.strip()
        if raw_s.startswith("[") and raw_s.endswith("]"):
            meta[key] = _inline_list(raw_s)
        elif raw_s == "":
            meta[key] = []  # a block list follows (or an empty value)
        else:
            meta[key] = _scalar(raw_s)
    for k, v in list(meta.items()):
        if v == []:
            # An empty value that no "- item" lines followed is an empty string,
            # except for keys that are lists by nature.
            if k not in ("tags", "aliases"):
                meta[k] = ""
    return meta, body


def _dump_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_dump_scalar(v) for v in value) + "]"
    return _dump_scalar(value)


def _dump_scalar(value):
    s = str(value)
    needs_quotes = (
        s == ""
        or s.strip() != s
        or s.lower() in _TRUE | _FALSE
        or re.fullmatch(r"-?\d+", s) is not None and not isinstance(value, int)
        or any(c in s for c in ",[]#:")
        and not re.fullmatch(r"\d{4}-\d\d-\d\d(T\d\d:\d\d(:\d\d)?)?", s)
    )
    if needs_quotes:
        return '"' + s.replace('"', "'") + '"'
    return s


def dump(meta, body):
    """Render meta + body back into note text. Key order is kept."""
    if not meta:
        return body
    out = [FENCE]
    for key, value in meta.items():
        out.append(f"{key}: {_dump_value(value)}")
    out.append(FENCE)
    text = "\n".join(out) + "\n"
    if body and not body.startswith("\n"):
        text += body
    else:
        text += body.lstrip("\n")
    return text
