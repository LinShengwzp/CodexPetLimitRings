"""Offline preview of the dithered glass/shadow badge on several backgrounds.

Renders exactly what rings/glass.py plans plus the ring arcs and the demo
label, composited over simulated wallpapers (no Tk, no screen capture), and
writes PNG files for visual tuning. Pure standard library.

Usage: python scripts/glass_preview.py [config.json]
Outputs: logs/glass_preview.png and logs/glass_preview_zoom.png
"""
from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rings.config import load_config  # noqa: E402
from rings.glass import plan_glass  # noqa: E402

FONT3X5 = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "011", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "001"),
    "/": ("001", "001", "010", "100", "100"),
}


def hex_rgb(value: str) -> tuple[int, int, int]:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def backgrounds():
    light_a, light_b = hex_rgb("#f2eef8"), hex_rgb("#dcd4ea")
    dark_a, dark_b = hex_rgb("#332f3f"), hex_rgb("#211e2b")
    pink_a, teal_a = hex_rgb("#e8b4c8"), hex_rgb("#9ccbd8")
    return [
        ("light", lambda x, y, w, h: mix(light_a, light_b, y / h)),
        ("dark", lambda x, y, w, h: mix(dark_a, dark_b, y / h)),
        ("photo", lambda x, y, w, h: mix(
            mix(pink_a, teal_a, x / w), (40, 44, 66), ((x + y) / (w + h)) * 0.45)),
        ("checker", lambda x, y, w, h: (235, 233, 238) if ((x // 8 + y // 8) & 1) else (168, 164, 176)),
    ]


def render_panel(conf, scale, bg_fn, margin=6):
    rings = conf["rings"]
    outer, inner = rings["outer"], rings["inner"]
    glass = conf["glass"]
    plan = plan_glass(outer["diameter"], outer["stroke"],
                     inner["diameter"], inner["stroke"], glass, scale)
    n = int(math.ceil(max(plan.pad_units + outer["diameter"] / 2, 8) * scale)) + margin
    w = h = 2 * n
    cx = cy = n
    pix = [[bg_fn(x, y, w, h) for x in range(w)] for y in range(h)]

    def put(x, y, color):
        if 0 <= x < w and 0 <= y < h:
            pix[y][x] = color

    # 1) dithered glass/shadow runs (same data the Tk canvas draws)
    for x0, x1, y, color in plan.runs:
        rgb = hex_rgb(color)
        for x in range(cx + x0, cx + x1 + 1):
            put(x, cy + y, rgb)

    # 2) ring annuli: track circle plus clockwise progress arc from 12 o'clock
    def draw_ring(style, pct, color):
        r = style["diameter"] * scale / 2
        stroke = max(1, round(style["stroke"] * scale))
        track = hex_rgb(conf["rings"]["trackColor"])
        prog = hex_rgb(color)
        lo, hi = r - stroke / 2 - 0.35, r + stroke / 2 + 0.35
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx + 0.5 - 0.5, y - cy + 0.5 - 0.5)
                if lo <= d <= hi:
                    theta = math.degrees(math.atan2(y - cy, x - cx))  # screen angle, y down
                    end = -90.0 + pct * 3.6
                    inside = (theta - end) % 360.0 <= 90.0 + 0.001 and theta != end
                    put(x, y, prog if inside else track)

    draw_ring(outer, 41, conf["rings"]["outer"]["color"])
    draw_ring(inner, 91, conf["rings"]["inner"]["color"])

    # 3) demo label with a tiny 3x5 font (stand-in for the Tk text item)
    label = f"41{conf['text']['separator']}91"
    glyphs = [FONT3X5[ch] for ch in label]
    gw = sum(len(g[0]) + 1 for g in glyphs) - 1
    tx = cx - gw // 2
    ty = cy - 2
    tcol = hex_rgb(conf["text"]["color"])
    for glyph in glyphs:
        for ry, row in enumerate(glyph):
            for rx, bit in enumerate(row):
                if bit == "1":
                    put(tx + rx, ty + ry, tcol)
        tx += len(glyph[0]) + 1
    return pix, w, h


def write_png(path: Path, pix, w, h):
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in pix)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))
    path.write_bytes(data)


def main() -> int:
    conf = load_config(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    bgs = backgrounds()
    scales = [1.0, 1.5]
    gap = 10
    panels = []
    for scale in scales:
        row = []
        for _, bg in bgs:
            row.append(render_panel(conf, scale, bg))
        panels.append(row)
    ph = max(p[2] for row in panels for p in row)
    pw = max(p[1] for row in panels for p in row)
    W = len(bgs) * pw + (len(bgs) - 1) * gap
    H = len(scales) * ph + (len(scales) - 1) * gap
    canvas = [[(72, 68, 84)] * W for _ in range(H)]
    for ry, row in enumerate(panels):
        for rx, (pix, w, h) in enumerate(row):
            y0 = ry * (ph + gap) + (ph - h) // 2
            x0 = rx * (pw + gap) + (pw - w) // 2
            for y in range(h):
                for x in range(w):
                    canvas[y0 + y][x0 + x] = pix[y][x]
    out = ROOT / "logs" / "glass_preview.png"
    out.parent.mkdir(exist_ok=True)
    write_png(out, canvas, W, H)
    print(f"wrote {out} ({W}x{H})")

    zoom, zw, zh = panels[0][0]
    z = 3
    big = [[zoom[y // z][x // z] for x in range(zw * z)] for y in range(zh * z)]
    out2 = ROOT / "logs" / "glass_preview_zoom.png"
    write_png(out2, big, zw * z, zh * z)
    print(f"wrote {out2} ({zw * z}x{zh * z})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
