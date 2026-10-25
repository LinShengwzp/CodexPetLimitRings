"""Render a tiny faux-frosted-glass circle with a soft shadow.

Standard library only. Encodes an RGBA PNG for Tk 8.6 PhotoImage so the
background need not be an opaque Canvas oval. It does NOT capture the desktop
or blur content behind the pet.
"""
from __future__ import annotations

import math
import struct
import zlib


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _over(back: tuple[float, float, float, float],
          front_rgb: tuple[int, int, int],
          front_alpha: float) -> tuple[float, float, float, float]:
    """Unpremultiplied source-over compositing, channels normalized to 0..255."""
    alpha = max(0.0, min(1.0, front_alpha))
    if alpha <= 0:
        return back
    br, bg, bb, ba = back
    out_a = alpha + ba * (1 - alpha)
    if out_a <= 0:
        return 0.0, 0.0, 0.0, 0.0
    return (
        (front_rgb[0] * alpha + br * ba * (1 - alpha)) / out_a,
        (front_rgb[1] * alpha + bg * ba * (1 - alpha)) / out_a,
        (front_rgb[2] * alpha + bb * ba * (1 - alpha)) / out_a,
        out_a,
    )


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def render_glass_rgba(
    size: int, outer_diameter: float, config: dict, scale: float = 1.0,
) -> bytes:
    """Produce row-major 8-bit RGBA bytes at *physical* display size.

    The glass is static and only regenerated when the theme or DPI changes.
    The shadows are analytic Gaussian falloff, not Gaussian-blurred desktop.
    """
    if not 1 <= size <= 1000:
        raise ValueError("Invalid canvas dimensions")
    fill_color = _rgb(config["fillColor"])
    shadow_color = _rgb(config["shadowColor"])
    rim_color = _rgb(config["rimColor"])
    shine_color = _rgb(config["highlightColor"])
    radius = (outer_diameter * scale) / 2 + config["outerMargin"] * scale
    sigma = max(0.8, config["shadowBlur"] * scale * 0.62)
    spread = config["shadowSpread"] * scale
    dx = config["shadowOffsetX"] * scale
    dy = config["shadowOffsetY"] * scale
    shadow_alpha = config["shadowOpacity"] / 100.0
    fill_alpha = config["fillOpacity"] / 100.0
    rim_alpha = config["rimOpacity"] / 100.0
    shine_alpha = config["highlightOpacity"] / 100.0
    cx = cy = size / 2.0
    ring_thickness = max(0.8, 1.15 * scale)
    data = bytearray(size * size * 4)
    pos = 0

    for y in range(size):
        yy = y + 0.5 - cy
        for x in range(size):
            xx = x + 0.5 - cx
            r = math.hypot(xx, yy)
            shadow_distance = max(0.0, math.hypot(xx - dx, yy - dy) - radius - spread)
            shadow = shadow_alpha * math.exp(-0.5 * (shadow_distance / sigma) ** 2)
            pixel = _over((0.0, 0.0, 0.0, 0.0), shadow_color, shadow)

            # 1px geometric antialias at the circular edge.
            coverage = max(0.0, min(1.0, radius + 0.5 - r))
            if coverage:
                # Soft cool-white center with a slight upper-left glow.
                light = max(0.0, 1.0 - math.hypot(xx + radius * 0.40, yy + radius * 0.54) / (radius * 2.0))
                pixel = _over(pixel, fill_color, coverage * fill_alpha)
                pixel = _over(pixel, shine_color, coverage * shine_alpha * light ** 2.0)
                rim_coverage = max(0.0, min(1.0, (r - (radius - ring_thickness - 0.5))))
                pixel = _over(pixel, rim_color, rim_alpha * coverage * rim_coverage)
            data[pos] = round(max(0.0, min(255.0, pixel[0])))
            data[pos + 1] = round(max(0.0, min(255.0, pixel[1])))
            data[pos + 2] = round(max(0.0, min(255.0, pixel[2])))
            data[pos + 3] = round(max(0.0, min(255.0, pixel[3] * 255)))
            pos += 4
    return bytes(data)


def encode_png(width: int, height: int, rgba: bytes) -> bytes:
    """Write a PNG using stdlib zlib, with all rows encoded as RGBA."""
    if len(rgba) != width * height * 4:
        raise ValueError("Incorrect RGBA buffer length")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack("!I", len(payload)) + kind + payload +
                struct.pack("!I", zlib.crc32(kind + payload) & 0xffffffff))

    stride = width * 4
    rows = b"".join(b"\x00" + rgba[y:y + stride] for y in range(0, len(rgba), stride))
    return (
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(rows, 6)) +
        chunk(b"IEND", b"")
    )


def render_glass_png(size: int, outer_diameter: float, config: dict, scale: float = 1.0) -> bytes:
    return encode_png(size, size, render_glass_rgba(size, outer_diameter, config, scale))
