"""External, hot-reloadable ring appearance configuration.

config.example.json is version-controlled; optional config.json is user-owned.
Invalid settings are ignored individually instead of crashing the desktop HUD.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
USER_CONFIG = ROOT / "config.json"
SAMPLE_CONFIG = ROOT / "config.example.json"

DEFAULT = {
    "rings": {
        "outer": {"diameter": 78, "stroke": 6, "color": "#aa8bda"},
        "inner": {"diameter": 54, "stroke": 5, "color": "#80b8e1"},
        "trackColor": "#d8d2e4",
        "warningColor": "#e6b15f",
        "criticalColor": "#ec797d",
        "unknownColor": "#97949f",
        "warningBelow": 20,
        "criticalBelow": 10,
    },
    "background": {
        "enabled": False,
        "color": "#f5f0fc",
        "borderColor": "#d0c2e4",
        "borderWidth": 0,
        "padding": 8,
    },
    "glass": {
        "enabled": True,
        "fillColor": "#f7f2ff",
        "fillOpacity": 56,
        "shadowColor": "#2d244d",
        "shadowOpacity": 24,
        "shadowBlur": 8,
        "shadowSpread": 1,
        "shadowOffsetX": 1,
        "shadowOffsetY": 3,
        "rimColor": "#ffffff",
        "rimOpacity": 74,
        "highlightColor": "#ffffff",
        "highlightOpacity": 35,
        "outerMargin": 2,
    },
    "text": {
        "fontFamily": "Segoe UI",
        "fontSize": 12,
        "bold": True,
        "color": "#706083",
        "separator": "/",
        "showPercentSign": False,
    },
    "animation": {
        "enabled": True,
        "fadeInMs": 220,
        "fadeOutMs": 130,
        "frameMs": 33,
    },
    "visibility": {
        "requireUIA": True,
    },
    "position": {
        "side": "left",
        "gap": 10,
        "verticalRatio": 0.12,
        "offsetX": 0,
        "offsetY": 0,
        "settleMs": 600,
    },
}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _number(value: Any, minimum: int, maximum: int, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        n = int(value)
        if minimum <= n <= maximum:
            return n
    except (ValueError, TypeError, OverflowError):
        pass
    return default


def _color(value: Any, default: str) -> str:
    return value if isinstance(value, str) and HEX_COLOR.fullmatch(value) else default


def _section(data: Any, key: str) -> dict:
    obj = data.get(key) if isinstance(data, dict) else None
    return obj if isinstance(obj, dict) else {}


def normalize(data: Any) -> dict:
    conf = deepcopy(DEFAULT)
    if not isinstance(data, dict):
        return conf
    r = _section(data, "rings")
    for name in ("outer", "inner"):
        raw = _section(r, name)
        ring = conf["rings"][name]
        ring["diameter"] = _number(raw.get("diameter"), 20, 240, ring["diameter"])
        ring["stroke"] = _number(raw.get("stroke"), 1, 20, ring["stroke"])
        ring["color"] = _color(raw.get("color"), ring["color"])
    # Guarantee a real inner ring separated from the outer ring.
    outer = conf["rings"]["outer"]
    inner = conf["rings"]["inner"]
    inner["diameter"] = min(inner["diameter"], max(10, outer["diameter"] - outer["stroke"] - inner["stroke"] - 4))
    for key in ("trackColor", "warningColor", "criticalColor", "unknownColor"):
        conf["rings"][key] = _color(r.get(key), conf["rings"][key])
    for key in ("warningBelow", "criticalBelow"):
        conf["rings"][key] = _number(r.get(key), 0, 100, conf["rings"][key])
    if conf["rings"]["criticalBelow"] > conf["rings"]["warningBelow"]:
        conf["rings"]["criticalBelow"] = conf["rings"]["warningBelow"]

    bg = _section(data, "background")
    conf["background"]["enabled"] = bg.get("enabled") if isinstance(bg.get("enabled"), bool) else conf["background"]["enabled"]
    for key in ("color", "borderColor"):
        conf["background"][key] = _color(bg.get(key), conf["background"][key])
    conf["background"]["borderWidth"] = _number(bg.get("borderWidth"), 0, 12, conf["background"]["borderWidth"])
    conf["background"]["padding"] = _number(bg.get("padding"), 0, 30, conf["background"]["padding"])

    glass = _section(data, "glass")
    if isinstance(glass.get("enabled"), bool):
        conf["glass"]["enabled"] = glass["enabled"]
    for key in ("fillColor", "shadowColor", "rimColor", "highlightColor"):
        conf["glass"][key] = _color(glass.get(key), conf["glass"][key])
    for key in ("fillOpacity", "shadowOpacity", "rimOpacity", "highlightOpacity"):
        conf["glass"][key] = _number(glass.get(key), 0, 100, conf["glass"][key])
    for key, low, high in (
        ("shadowBlur", 1, 24),
        ("shadowSpread", 0, 20),
        ("shadowOffsetX", -20, 20),
        ("shadowOffsetY", -20, 20),
        ("outerMargin", 0, 12),
    ):
        conf["glass"][key] = _number(glass.get(key), low, high, conf["glass"][key])

    t = _section(data, "text")
    if isinstance(t.get("fontFamily"), str) and 1 <= len(t["fontFamily"]) <= 100:
        conf["text"]["fontFamily"] = t["fontFamily"]
    conf["text"]["fontSize"] = _number(t.get("fontSize"), 7, 36, conf["text"]["fontSize"])
    if isinstance(t.get("bold"), bool):
        conf["text"]["bold"] = t["bold"]
    conf["text"]["color"] = _color(t.get("color"), conf["text"]["color"])
    if isinstance(t.get("separator"), str) and len(t["separator"]) <= 3:
        conf["text"]["separator"] = t["separator"]
    if isinstance(t.get("showPercentSign"), bool):
        conf["text"]["showPercentSign"] = t["showPercentSign"]

    animation = _section(data, "animation")
    if isinstance(animation.get("enabled"), bool):
        conf["animation"]["enabled"] = animation["enabled"]
    for key, low, high in (
        ("fadeInMs", 0, 1200),
        ("fadeOutMs", 0, 1200),
        ("frameMs", 15, 100),
    ):
        conf["animation"][key] = _number(
            animation.get(key), low, high, conf["animation"][key]
        )
    visibility = _section(data, "visibility")
    if isinstance(visibility.get("requireUIA"), bool):
        conf["visibility"]["requireUIA"] = visibility["requireUIA"]

    p = _section(data, "position")
    if p.get("side") in ("left", "right"):
        conf["position"]["side"] = p["side"]
    for key, low, high in (
        ("gap", 0, 100),
        ("offsetX", -2500, 2500),
        ("offsetY", -2500, 2500),
        ("settleMs", 150, 5000),
    ):
        conf["position"][key] = _number(p.get(key), low, high, conf["position"][key])
    try:
        vertical = float(p.get("verticalRatio"))
        if 0 <= vertical <= 1:
            conf["position"]["verticalRatio"] = vertical
    except (ValueError, TypeError, OverflowError):
        pass
    return conf


def load_config(path: Path | None = None) -> dict:
    file = path if path is not None else (USER_CONFIG if USER_CONFIG.exists() else SAMPLE_CONFIG)
    try:
        return normalize(json.loads(file.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, UnicodeError):
        return deepcopy(DEFAULT)


class ConfigWatcher:
    def __init__(self, path: Path | None = None):
        self.path = path
        self._signature: tuple | None = None
        self.value = deepcopy(DEFAULT)

    def refresh(self) -> bool:
        file = self.path or (USER_CONFIG if USER_CONFIG.exists() else SAMPLE_CONFIG)
        try:
            # File timestamps can have coarse resolution (Windows/network disks).
            # Two rapid edits may keep the same mtime and even file size.
            raw = file.read_bytes()
            signature = (str(file), raw[:131072])
        except OSError:
            signature = (str(file), None)
        if self._signature == signature:
            return False
        self._signature = signature
        value = load_config(file)
        if value == self.value:
            return False
        self.value = value
        return True
