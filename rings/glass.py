"""Faux-glass and soft-shadow planning via ordered dithering (Tk-safe).

IMPORTANT: Tk's -transparentcolor layered-window path makes every pixel either
exactly the key color (fully transparent) or fully opaque; partially
transparent PhotoImage PNG pixels render as a black matte on some Windows/Tk
builds. This module therefore simulates translucency differently: each
decoration layer is converted into a 4x4 ordered dither (Bayer matrix)
between *opaque* paint colors and the transparent key. The eye averages the
stipple with the desktop visible through the holes, so the drop shadow and
the frosted disc appear genuinely translucent over any wallpaper. No desktop
capture, Pillow, or per-pixel alpha is involved.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 4x4 ordered-dither matrix: 16 evenly spaced thresholds, dense enough that
# the stipple reads as a smooth tint even at 96 DPI badge sizes.
_BAYER4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def blend_hex(foreground: str, background: str, strength: float) -> str:
    """Blend solid colors; result is fully opaque and safe for Tk Canvas."""
    p = max(0.0, min(1.0, float(strength)))
    values = [
        round(int(background[i:i + 2], 16) * (1 - p) +
              int(foreground[i:i + 2], 16) * p)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{value:02x}" for value in values)


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = (x - edge0) / (edge1 - edge0)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def _pick_dither(layers, x: int, y: int) -> str | None:
    """Ordered-dither a stack of (color, alpha) layers, top layer first.

    Each layer gets a contiguous share of the dither cells proportional to
    its residual opacity, so overlapping layers composite exactly. Returns
    the opaque paint for this pixel, or None when the cell belongs to the
    transparent key (the desktop shows through the hole).
    """
    threshold = (_BAYER4[y & 3][x & 3] + 0.5) / 16.0
    used = 0.0
    for color, alpha in layers:
        share = (1.0 - used) * alpha
        if share <= 0.0:
            continue
        if threshold < used + share:
            return color
        used += share
    return None


@dataclass(frozen=True)
class GlassPlan:
    """Opaque 1px scanline runs relative to the badge center (Tk-safe).

    runs: (x0, x1, y, color) with x0..x1 inclusive, all integers in physical
    pixels. pad_units: required config-unit padding around the outer ring so
    every painted pixel fits inside the Tk window.
    """
    runs: tuple[tuple[int, int, int, str], ...]
    pad_units: float
    disc_radius: float
    shadow_extent: float


def plan_glass(
    outer_diameter: float,
    outer_stroke: float,
    inner_diameter: float,
    inner_stroke: float,
    config: dict,
    scale: float = 1.0,
) -> GlassPlan:
    """Plan a dithered soft shadow plus a frosted disc inside the inner ring.

    Geometry is centered on the scaled HUD canvas; every emitted pixel is
    either an opaque decoration color or simply not emitted (transparent key).
    """
    scale = max(0.25, float(scale))
    outer_radius = outer_diameter * scale / 2.0
    inner_radius = inner_diameter * scale / 2.0
    ring_edge = outer_radius + max(0.5, outer_stroke * scale / 2.0)

    gap = max(0.75, float(config["outerMargin"])) * scale
    spread = min(10.0, float(config["shadowSpread"])) * 0.5 * scale
    blur = min(18.0, max(1.5, float(config["shadowBlur"]))) * scale
    off_x = max(-20.0, min(20.0, float(config["shadowOffsetX"]))) * scale
    off_y = max(-20.0, min(20.0, float(config["shadowOffsetY"]))) * scale
    off_mag = math.hypot(off_x, off_y)
    off_cap = 14.0 * scale
    if off_mag > off_cap and off_mag > 0.0:
        k = off_cap / off_mag
        off_x *= k
        off_y *= k
        off_mag = off_cap

    r0 = ring_edge + gap + spread
    r1 = r0 + max(2.0, blur)
    shadow_alpha = _clamp01(config["shadowOpacity"] / 100.0)
    shadow_color = config["shadowColor"]

    r_disc = max(4.5 * scale, inner_radius - inner_stroke * scale / 2.0 - 1.8 * scale)
    rim_width = max(1.1, 1.4 * scale)
    band_width = max(1.6, 2.4 * scale)
    r_rim_in = r_disc - rim_width
    r_band_in = max(r_disc * 0.3, r_rim_in - band_width)

    fill_alpha = _clamp01(config["fillOpacity"] / 100.0)
    rim_alpha = _clamp01(config["rimOpacity"] / 100.0)
    hl_alpha = _clamp01(config["highlightOpacity"] / 100.0)
    shade_alpha = rim_alpha * 0.30
    fill_color = config["fillColor"]
    rim_color = config["rimColor"]
    hl_color = config["highlightColor"]
    shade_color = blend_hex(shadow_color, fill_color, 0.42)
    feather = max(0.8, 0.9 * scale)
    inv_disc = 1.0 / (2.0 * r_disc)

    def pixel(x: int, y: int) -> str | None:
        fx = x + 0.5
        fy = y + 0.5
        d = math.hypot(fx, fy)
        if d <= r_disc + feather + 1.0:
            layers = []
            cover = _clamp01((r_disc - d) / feather + 0.5)
            if cover > 0.0:
                if fill_alpha > 0.0:
                    # Frosted tint, slightly denser at the top (lit side).
                    v = _clamp01((fy + r_disc) * inv_disc)
                    a = _clamp01(fill_alpha * (1.15 - 0.30 * v)) * cover
                    if a > 0.004:
                        layers.append((fill_color, a))
                if rim_alpha > 0.0:
                    cov = (_smoothstep(r_rim_in - 0.55, r_rim_in + 0.55, d)
                           * (1.0 - _smoothstep(r_disc + 0.15, r_disc + 0.95, d)))
                    a = rim_alpha * cov
                    if a > 0.004:
                        layers.append((rim_color, a))
                if d > 0.0 and (hl_alpha > 0.0 or shade_alpha > 0.004):
                    cov = (_smoothstep(r_band_in - 0.55, r_band_in + 0.55, d)
                           * (1.0 - _smoothstep(r_rim_in - 0.55, r_rim_in + 0.55, d)))
                    if cov > 0.0:
                        ux, uy = fx / d, fy / d
                        t = (d - r_band_in) / max(0.75, r_rim_in - r_band_in)
                        fade = (1.0 - _clamp01(t)) ** 1.5
                        # Top-left crescent (light source) and a muted
                        # bottom-right shade for glass-ball depth.
                        w_hl = max(0.0, -(ux + uy) * 0.7071067811865476) ** 1.6
                        a = hl_alpha * cov * fade * w_hl
                        if a > 0.004:
                            layers.append((hl_color, a))
                        w_sh = max(0.0, (ux + uy) * 0.7071067811865476) ** 1.8
                        a = shade_alpha * cov * fade * w_sh
                        if a > 0.004:
                            layers.append((shade_color, a))
            if layers:
                return _pick_dither(layers, x, y)
            if cover > 0.02:
                # Inside the frosted disc: never let the cast shadow stipple
                # poke through the badge itself.
                return None
        ds = math.hypot(fx - off_x, fy - off_y)
        if ds < r1:
            u = (ds - r0) / (r1 - r0)
            if u < 1.0:
                # Dense at the badge silhouette, easing out to nothing.
                a = shadow_alpha * (1.0 - u) ** 1.8 * _smoothstep(r0 - 0.6, r0 + 0.6, ds)
                if a > 0.004:
                    return shadow_color if _pick_dither(((shadow_color, a),), x, y) else None
        return None

    extent = max(r1 + off_mag + 1.5, ring_edge + 0.75)
    n = int(math.ceil(extent))
    runs: list[tuple[int, int, int, str]] = []
    for y in range(-n, n + 1):
        start = None
        color: str | None = None
        for x in range(-n, n + 1):
            c = pixel(x, y)
            if c != color:
                if color is not None:
                    runs.append((start, x - 1, y, color))
                color = c
                start = x
        if color is not None:
            runs.append((start, n, y, color))

    pad_units = extent / scale - outer_diameter / 2.0
    return GlassPlan(
        runs=tuple(runs),
        pad_units=pad_units,
        disc_radius=r_disc,
        shadow_extent=r1,
    )
