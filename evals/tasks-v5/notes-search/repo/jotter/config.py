"""Where the vault lives and a few user settings.

The vault is `--vault DIR`, else `$JOTTER_VAULT`, else `~/Notes`.
"""

import os
from pathlib import Path

DEFAULT_VAULT = Path.home() / "Notes"

# Front-matter keys jotter itself writes. Anything else is kept as-is.
KNOWN_KEYS = ("title", "tags", "created", "updated", "archived", "aliases", "source")

# How many characters of body `jotter list --long` shows.
EXCERPT_CHARS = 80


def vault_path(arg=None):
    """Resolve the vault directory from the CLI flag or the environment."""
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("JOTTER_VAULT")
    if env:
        return Path(env).expanduser()
    return DEFAULT_VAULT


def editor():
    """The editor `jotter new --edit` opens. Falls back to vi."""
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
