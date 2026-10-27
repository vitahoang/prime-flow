"""Map job kinds to the functions that run them.

A handler is any callable that takes the job's payload (a dict) and returns
nothing. Raising means the job failed. Handlers should be idempotent where
they can be: a job can be requeued by hand after a partial run.
"""

from __future__ import annotations

import importlib
import re
from typing import Any, Callable, Iterator

from .errors import UnknownJobKind

Handler = Callable[[dict[str, Any]], Any]

_KIND = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


class Registry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, kind: str, fn: Handler | None = None):
        """Register ``fn`` for ``kind``. Works as a call or a decorator::

            registry.register("email.send", send_email)

            @registry.register("image.thumbnail")
            def thumbnail(payload): ...
        """
        if not _KIND.match(kind):
            raise ValueError(f"bad job kind {kind!r}: use dotted lowercase names like 'email.send'")

        def add(f: Handler) -> Handler:
            if kind in self._handlers and self._handlers[kind] is not f:
                raise ValueError(f"job kind {kind!r} already has a handler")
            self._handlers[kind] = f
            return f

        return add(fn) if fn is not None else add

    def get(self, kind: str) -> Handler:
        try:
            return self._handlers[kind]
        except KeyError:
            raise UnknownJobKind(kind) from None

    def unregister(self, kind: str) -> None:
        self._handlers.pop(kind, None)

    def kinds(self) -> list[str]:
        return sorted(self._handlers)

    def __contains__(self, kind: object) -> bool:
        return kind in self._handlers

    def __iter__(self) -> Iterator[str]:
        return iter(self.kinds())

    def __len__(self) -> int:
        return len(self._handlers)

    def load_modules(self, modules: list[str]) -> None:
        """Import each module and call its ``register(registry)`` function."""
        for name in modules:
            mod = importlib.import_module(name)
            setup = getattr(mod, "register", None)
            if setup is None:
                raise ValueError(f"handler module {name!r} has no register(registry) function")
            setup(self)
