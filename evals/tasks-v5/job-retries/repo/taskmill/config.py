"""Configuration, read from a TOML file.

Lookup order for the file: ``--config`` on the command line, then
``$TASKMILL_CONFIG``, then ``./config.toml``. A missing file means defaults.
``$TASKMILL_DB`` overrides ``database`` wherever it came from.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError

DEFAULT_PATH = "config.toml"


@dataclass
class WebhookSettings:
    timeout: float = 10.0
    user_agent: str = "taskmill/0.6"


@dataclass
class EmailSettings:
    host: str = "localhost"
    port: int = 25
    sender: str = "noreply@example.com"
    dry_run: bool = False


@dataclass
class Config:
    database: str = "taskmill.db"
    workers: int = 1
    poll_interval: float = 1.0
    log_level: str = "INFO"
    queues: list[str] = field(default_factory=list)
    handler_modules: list[str] = field(default_factory=lambda: ["taskmill.handlers"])
    purge_after_days: int = 14
    webhook: WebhookSettings = field(default_factory=WebhookSettings)
    email: EmailSettings = field(default_factory=EmailSettings)
    source: str | None = None

    def validate(self) -> "Config":
        if self.workers < 1:
            raise ConfigError("workers must be at least 1")
        if self.workers > 32:
            raise ConfigError("workers above 32 is almost certainly a typo")
        if self.poll_interval <= 0:
            raise ConfigError("poll_interval must be positive")
        if self.log_level.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ConfigError(f"unknown log_level {self.log_level!r}")
        if self.purge_after_days < 1:
            raise ConfigError("purge_after_days must be at least 1")
        return self


_SECTIONS = {"webhook": WebhookSettings, "email": EmailSettings}


def _build(data: dict[str, Any], source: str | None) -> Config:
    data = dict(data)
    taskmill = data.pop("taskmill", {})
    known = {f for f in Config.__dataclass_fields__} - {"source", *_SECTIONS}
    unknown = set(taskmill) - known
    if unknown:
        raise ConfigError(f"unknown setting(s) in [taskmill]: {', '.join(sorted(unknown))}")
    kwargs: dict[str, Any] = dict(taskmill)
    for name, cls in _SECTIONS.items():
        section = data.pop(name, {})
        bad = set(section) - set(cls.__dataclass_fields__)
        if bad:
            raise ConfigError(f"unknown setting(s) in [{name}]: {', '.join(sorted(bad))}")
        kwargs[name] = cls(**section)
    if data:
        raise ConfigError(f"unknown section(s): {', '.join(sorted(data))}")
    try:
        return Config(source=source, **kwargs)
    except TypeError as exc:
        raise ConfigError(str(exc)) from None


def load(path: str | os.PathLike[str] | None = None) -> Config:
    explicit = path is not None or "TASKMILL_CONFIG" in os.environ
    path = Path(path or os.environ.get("TASKMILL_CONFIG") or DEFAULT_PATH)
    if path.exists():
        with open(path, "rb") as fh:
            try:
                data = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(f"{path}: {exc}") from None
        cfg = _build(data, str(path))
    elif explicit:
        raise ConfigError(f"config file not found: {path}")
    else:
        cfg = Config()
    if os.environ.get("TASKMILL_DB"):
        cfg.database = os.environ["TASKMILL_DB"]
    return cfg.validate()
