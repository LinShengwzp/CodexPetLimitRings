"""Safe faux-glass palette for Tk color-key overlays.

IMPORTANT: Tk's -transparentcolor layered-window path on some Windows/Tk
builds draws a black matte for partially transparent PhotoImage PNG pixels.
This module intentionally uses only *opaque* Tk canvas shape colors. The
area outside the drawn shapes remains the existing transparent color key.
No desktop capture, Pillow, or per-pixel alpha is involved.
"""
from __future__ import annotations

from dataclasses import dataclass


def blend_hex(foreground: str, background: str, strength: float) -> str:
    """Blend solid colors; result is fully opaque and safe for Tk Canvas."""
    p = max(0.0, min(1.0, float(strength)))
    values = [
        round(int(background[i:i + 2], 16) * (1 - p) +
              int(foreground[i:i + 2], 16) * p)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{value:02x}" for value in values)


@dataclass(frozen=True)
class GlassPlan:
    """Geometry is centered on the already scaled HUD canvas."""
    shadow_radii: tuple[float, ...]
    shadow_colors: tuple[str, ...]
    disc_radius: float
    disc_fill: str
    disc_rim: str
    highlight: str
    highlight_opacity: int


def plan_glass(
    outer_diameter: float,
    inner_diameter: float,
    inner_stroke: float,
    config: dict,
    scale: float = 1.0,
) -> GlassPlan:
    """Keep the pastel disc *inside* the inner ring, never make a giant halo.

    Opacity settings tune simulated color softness, not genuine per-pixel
    transparency. This is a deliberate compatibility tradeoff.
    """
    outer_radius = outer_diameter * scale / 2.0
    inner_radius = inner_diameter * scale / 2.0
    glow = config["shadowOpacity"] / 100.0
    fill = config["fillColor"]
    shadow = config["shadowColor"]
    # Width less than 9 physical pixels outside the progress ring. The last
    # contour is extremely faint; no broad dark/matte annulus is drawn.
    radii = (outer_radius + 5.5 * scale,
             outer_radius + 3.5 * scale,
             outer_radius + 1.5 * scale)
    colors = tuple(
        blend_hex(shadow, fill, glow * weight)
        for weight in (0.18, 0.32, 0.48)
    )
    disc_radius = max(
        5.0 * scale,
        inner_radius - (inner_stroke * scale / 2.0) - 1.8 * scale,
    )
    # The fill is a single safe, opaque pastel. Let fillOpacity affect its
    # tint; Tk cannot correctly render a partially transparent PNG here.
    disc_fill = blend_hex(fill, "#ece7f5",
                          max(0.0, min(1.0, config["fillOpacity"] / 100.0)))
    disc_rim = blend_hex(config["rimColor"], disc_fill,
                         min(0.85, config["rimOpacity"] / 100.0))
    return GlassPlan(
        shadow_radii=radii,
        shadow_colors=colors,
        disc_radius=disc_radius,
        disc_fill=disc_fill,
        disc_rim=disc_rim,
        highlight=config["highlightColor"],
        highlight_opacity=config["highlightOpacity"],
    )
