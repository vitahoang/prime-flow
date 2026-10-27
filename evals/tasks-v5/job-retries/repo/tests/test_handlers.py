import io
import urllib.error
from email.message import Message

import pytest

from taskmill import config
from taskmill.errors import RateLimited
from taskmill.handlers import email, thumbnails, webhooks


def test_build_email():
    msg = email.build_message({"to": "a@b.c", "subject": "S", "body": "B"}, config.EmailSettings())
    assert msg["To"] == "a@b.c" and msg.get_content().strip() == "B"


def test_email_missing_fields():
    with pytest.raises(ValueError):
        email.build_message({"to": "a@b.c"}, config.EmailSettings())


def test_send_email_uses_transport():
    sent = []
    old = email.set_transport(lambda msg, s: sent.append(msg["Subject"]))
    try:
        email.send_email({"to": "a@b.c", "subject": "S", "body": "B"})
    finally:
        email.set_transport(old)
    assert sent == ["S"]


def test_thumbnail(tmp_path):
    src = tmp_path / "in.ppm"
    w, h = 40, 20
    src.write_bytes(f"P6\n# made by test\n{w} {h}\n255\n".encode() + bytes((i * 7) % 256 for i in range(w * h * 3)))
    dest = tmp_path / "out" / "t.ppm"
    thumbnails.make_thumbnail({"src": str(src), "dest": str(dest), "max_side": 10})
    magic, tw, th, pixels = thumbnails.read_netpbm(dest)
    assert (magic, tw, th) == ("P6", 10, 5)
    assert len(pixels) == 10 * 5 * 3


def test_fit():
    assert thumbnails.fit(100, 50, 128) == (100, 50)
    assert thumbnails.fit(1000, 500, 100) == (100, 50)


class FakeResp:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_webhook_delivers():
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, req.get_header("Content-type")))
        return FakeResp()

    old = webhooks.set_opener(opener)
    try:
        webhooks.deliver({"url": "https://partner.example/hook", "event": "order.shipped"})
    finally:
        webhooks.set_opener(old)
    assert seen == [("https://partner.example/hook", "application/json")]


def test_webhook_429_raises_rate_limited():
    def opener(req, timeout):
        hdrs = Message()
        hdrs["Retry-After"] = "120"
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs, io.BytesIO())

    old = webhooks.set_opener(opener)
    try:
        with pytest.raises(RateLimited) as info:
            webhooks.deliver({"url": "https://partner.example/hook", "event": "e"})
    finally:
        webhooks.set_opener(old)
    assert info.value.retry_after == 120


def test_parse_retry_after():
    assert webhooks.parse_retry_after("30") == 30
    assert webhooks.parse_retry_after(None) == webhooks.DEFAULT_RETRY_AFTER
    assert webhooks.parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") == webhooks.DEFAULT_RETRY_AFTER
