"""``image.thumbnail``: shrink a PGM/PPM image to fit a box.

Payload: ``{"src": "in.ppm", "dest": "out.ppm", "max_side": 128}``.
Only binary netpbm (P5/P6) is supported; the upload service converts
everything to that before enqueueing. Nearest-neighbour sampling: these are
previews, not prints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..registry import Registry

DEFAULT_MAX_SIDE = 128


def _read_token(data: bytes, pos: int) -> tuple[bytes, int]:
    while pos < len(data):
        c = data[pos:pos + 1]
        if c == b"#":
            while pos < len(data) and data[pos:pos + 1] not in (b"\n", b"\r"):
                pos += 1
        elif c.isspace():
            pos += 1
        else:
            break
    start = pos
    while pos < len(data) and not data[pos:pos + 1].isspace():
        pos += 1
    return data[start:pos], pos


def read_netpbm(path: Path) -> tuple[str, int, int, bytes]:
    data = path.read_bytes()
    magic, pos = _read_token(data, 0)
    if magic not in (b"P5", b"P6"):
        raise ValueError(f"{path}: not a binary PGM/PPM file")
    w, pos = _read_token(data, pos)
    h, pos = _read_token(data, pos)
    maxval, pos = _read_token(data, pos)
    if int(maxval) > 255:
        raise ValueError(f"{path}: 16-bit images are not supported")
    pixels = data[pos + 1:]
    return magic.decode(), int(w), int(h), pixels


def fit(width: int, height: int, max_side: int) -> tuple[int, int]:
    if width <= max_side and height <= max_side:
        return width, height
    scale = max_side / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def resize(pixels: bytes, width: int, height: int, channels: int, new_w: int, new_h: int) -> bytes:
    out = bytearray(new_w * new_h * channels)
    for y in range(new_h):
        sy = min(height - 1, y * height // new_h)
        for x in range(new_w):
            sx = min(width - 1, x * width // new_w)
            src = (sy * width + sx) * channels
            dst = (y * new_w + x) * channels
            out[dst:dst + channels] = pixels[src:src + channels]
    return bytes(out)


def make_thumbnail(payload: dict[str, Any]) -> None:
    src, dest = Path(payload["src"]), Path(payload["dest"])
    max_side = int(payload.get("max_side", DEFAULT_MAX_SIDE))
    magic, w, h, pixels = read_netpbm(src)
    channels = 3 if magic == "P6" else 1
    new_w, new_h = fit(w, h, max_side)
    small = resize(pixels, w, h, channels, new_w, new_h)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(f"{magic}\n{new_w} {new_h}\n255\n".encode() + small)
    tmp.replace(dest)


def register(registry: Registry) -> None:
    registry.register("image.thumbnail", make_thumbnail)
