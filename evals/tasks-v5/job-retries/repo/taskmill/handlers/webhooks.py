"""``webhook.deliver``: POST a JSON event to a partner's endpoint.

Payload: ``{"url": "https://...", "event": "order.shipped", "data": {...}}``.
Partners are told to treat deliveries as at-least-once and to dedupe on the
``X-Taskmill-Delivery`` header, but several of them don't.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Callable

from .. import config as config_mod
from ..errors import RateLimited
from ..registry import Registry

log = logging.getLogger("taskmill.handlers.webhooks")

DEFAULT_RETRY_AFTER = 60.0

Opener = Callable[[urllib.request.Request, float], Any]


def _urlopen(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout)


_open: Opener = _urlopen


def set_opener(fn: Opener) -> Opener:
    global _open
    old, _open = _open, fn
    return old


def parse_retry_after(value: str | None) -> float:
    """Seconds from a Retry-After header. HTTP dates aren't worth supporting:
    none of our partners send them."""
    if not value:
        return DEFAULT_RETRY_AFTER
    try:
        return max(0.0, float(value))
    except ValueError:
        return DEFAULT_RETRY_AFTER


def build_request(payload: dict[str, Any], settings: config_mod.WebhookSettings) -> urllib.request.Request:
    body = json.dumps({"event": payload["event"], "data": payload.get("data", {})}, sort_keys=True).encode()
    req = urllib.request.Request(payload["url"], data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", settings.user_agent)
    if payload.get("delivery_id"):
        req.add_header("X-Taskmill-Delivery", str(payload["delivery_id"]))
    return req


def deliver(payload: dict[str, Any]) -> None:
    settings = config_mod.load().webhook
    req = build_request(payload, settings)
    try:
        with _open(req, settings.timeout) as resp:
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimited(parse_retry_after(exc.headers.get("Retry-After")),
                              f"{payload['url']} returned 429") from None
        raise
    if not 200 <= status < 300:
        raise RuntimeError(f"{payload['url']} returned {status}")
    log.info("delivered %s to %s", payload["event"], payload["url"])


def register(registry: Registry) -> None:
    registry.register("webhook.deliver", deliver)
