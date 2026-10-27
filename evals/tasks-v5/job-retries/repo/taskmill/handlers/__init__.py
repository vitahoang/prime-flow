"""Built-in job handlers.

``config.handler_modules`` lists modules whose ``register(registry)`` is
called at worker start-up. This package registers all the built-ins.
"""

from __future__ import annotations

from ..registry import Registry
from . import email, thumbnails, webhooks


def register(registry: Registry) -> None:
    email.register(registry)
    thumbnails.register(registry)
    webhooks.register(registry)
