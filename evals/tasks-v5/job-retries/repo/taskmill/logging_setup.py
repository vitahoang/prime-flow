"""Logging configuration shared by the CLI and worker processes."""

from __future__ import annotations

import logging
import os
import sys

FORMAT = "%(asctime)s %(levelname)-7s %(name)s [%(process)d] %(message)s"


def configure(level: str = "INFO", stream=None) -> None:
    level = os.environ.get("TASKMILL_LOG_LEVEL", level).upper()
    root = logging.getLogger("taskmill")
    root.setLevel(level)
    if not any(getattr(h, "_taskmill", False) for h in root.handlers):
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(logging.Formatter(FORMAT))
        handler._taskmill = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.propagate = False
