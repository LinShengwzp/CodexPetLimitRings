"""Read the Codex Desktop /pet placement without opening or changing any secrets.

Codex stores the actual avatar overlay placement in its global UI state.
A large native transparent host HWND alone is *not* the mascot rectangle.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Rect


@dataclass(frozen=True)
class PetPlacement:
    window: Rect
    mascot: Rect
    has_mascot_geometry: bool
    persisted_mascot_origin: bool


def _obj(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def _number(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    try:
        n = float(x)
        return n if math.isfinite(n) and abs(n) < 100000 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _detail_candidates(bounds: dict) -> list[tuple[dict, bool]]:
    """Prioritize mascot geometry for active display, then resolution, then fallback."""
    results: list[tuple[dict, bool]] = []
    by_display = _obj(bounds.get("byDisplayId"))
    display_id = str(bounds.get("displayId", ""))
    display = _obj(bounds.get("displayBounds"))
    width = _number(display.get("width"))
    height = _number(display.get("height"))
    resolution = f"{round(width)}x{round(height)}" if width and height else ""
    by_resolution = _obj(bounds.get("byResolution"))
    suggested = [
        (by_display.get(display_id), False),
        (by_resolution.get(resolution), False),
        (bounds, True),
        *((value, False) for value in by_display.values()),
        *((value, False) for value in by_resolution.values()),
    ]
    for raw, top in suggested:
        d = _obj(raw)
        if _number(d.get("width")) and _number(d.get("height")):
            results.append((d, top))
    # Keep a mascot-aware candidate before stale geometry-only candidates.
    return sorted(results, key=lambda item: _has_mascot(item[0]), reverse=True)


def _has_mascot(d: dict) -> bool:
    mascot = _obj(d.get("mascot") or d.get("anchor"))
    return all(_number(mascot.get(k)) is not None for k in ("left", "top", "width", "height"))


def parse_pet_placement(state: Any) -> PetPlacement | None:
    root = _obj(state)
    if root.get("electron-avatar-overlay-open") is not True:
        return None
    bounds = _obj(root.get("electron-avatar-overlay-bounds"))
    top_x = _number(bounds.get("x"))
    top_y = _number(bounds.get("y"))
    for detail, top in _detail_candidates(bounds):
        w = _number(detail.get("width"))
        h = _number(detail.get("height"))
        x = top_x if top_x is not None else _number(detail.get("x"))
        y = top_y if top_y is not None else _number(detail.get("y"))
        if None in (x, y, w, h) or not 2 < w < 6000 or not 2 < h < 4000:
            continue
        window = Rect(round(x), round(y), round(x + w), round(y + h))
        geometry = _has_mascot(detail)
        mascot_data = _obj(detail.get("mascot") or detail.get("anchor"))
        if geometry:
            left = _number(mascot_data.get("left"))
            top_px = _number(mascot_data.get("top"))
            mascot_w = _number(mascot_data.get("width"))
            mascot_h = _number(mascot_data.get("height"))
            if mascot_w is None or mascot_h is None or not 2 < mascot_w < 2000 or not 2 < mascot_h < 2000:
                geometry = False
        if geometry:
            mascot = Rect(round(x + left), round(y + top_px),
                          round(x + left + mascot_w), round(y + top_px + mascot_h))
        else:
            # Old Codex builds persist avatar X/Y directly, but omit geometry.
            # This is only a fallback, not a claim about its actual PNG bounds.
            mascot = Rect(round(x), round(y), round(x + 128), round(y + 139))
        return PetPlacement(
            window=window, mascot=mascot, has_mascot_geometry=geometry,
            persisted_mascot_origin=not _has_mascot(bounds),
        )
    return None


def state_file() -> Path:
    home = Path(os.path.expandvars(os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex"))))
    return home / ".codex-global-state.json"


def read_pet_placement(path: Path | None = None) -> PetPlacement | None:
    file = path if path is not None else state_file()
    try:
        return parse_pet_placement(json.loads(file.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, UnicodeError):
        return None
