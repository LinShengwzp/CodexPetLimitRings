"""Manual mascot center calibration for Codex builds without mascot geometry.

A calibration stores offsets from the transparent host's right/bottom edges.
This is local UI metadata; it contains no Codex credentials.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .core import Rect


def settings_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodexPetLimitRings" / "settings.json"


def read_settings() -> dict:
    try:
        parsed = json.loads(settings_path().read_text(encoding="utf-8-sig"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def write_settings(changes: dict) -> None:
    file = settings_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    data = read_settings()
    data.update(changes)
    temp = file.with_name(file.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(file)


def create_anchor(host: Rect, cursor_x: int, cursor_y: int) -> dict:
    if host.width <= 0 or host.height <= 0:
        raise ValueError("Invalid pet host geometry")
    return {
        "version": 1,
        "rightInset": host.right - cursor_x,
        "bottomInset": host.bottom - cursor_y,
        "mascotWidth": 138,
        "mascotHeight": 155,
    }


def sprite_from_anchor(host: Rect, anchor: Any) -> Rect | None:
    if not isinstance(anchor, dict) or anchor.get("version") != 1:
        return None
    try:
        right_inset = int(anchor["rightInset"])
        bottom_inset = int(anchor["bottomInset"])
        width = int(anchor.get("mascotWidth", 138))
        height = int(anchor.get("mascotHeight", 155))
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
    if not -8000 <= right_inset <= 8000 or not -8000 <= bottom_inset <= 8000:
        return None
    if not 50 <= width <= 600 or not 50 <= height <= 600:
        return None
    cx = host.right - right_inset
    cy = host.bottom - bottom_inset
    return Rect(cx - width // 2, cy - height // 2, cx - width // 2 + width, cy - height // 2 + height)


def move_anchor(
    anchor: dict, dx: int, dy: int, *,
    host_dx: int = 0, host_dy: int = 0,
) -> dict:
    """Translate an avatar by cursor delta without double-counting host motion.

    The calibrated avatar center is (host.right - rightInset,
    host.bottom - bottomInset). Therefore the new inset must change by
    host_delta - cursor_delta. When host and mouse both move 215 px, the
    inset must stay constant, not move another 215 px.
    """
    updated = dict(anchor)
    updated["rightInset"] = int(anchor["rightInset"]) + host_dx - dx
    updated["bottomInset"] = int(anchor["bottomInset"]) + host_dy - dy
    return updated
