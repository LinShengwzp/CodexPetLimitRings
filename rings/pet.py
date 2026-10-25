"""Discover Codex Desktop Pet HWND, verify it against persisted avatar placement.

The actual sprite may occupy only a tiny area of a 888x1080 transparent host.
The UI state supplies sprite placement; Win32 confirms the host is visible.
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass

from .core import Rect
from .state import PetPlacement, read_pet_placement
from .uia import UIAMascotWatcher


@dataclass(frozen=True)
class Pet:
    handle: int
    rect: Rect                # Visible mascot, NOT the full transparent host.
    work_area: Rect
    dpi: int
    process: str
    host_rect: Rect
    precise: bool
    source: str


def intersects(a: Rect, b: Rect) -> bool:
    return a.left < b.right and b.left < a.right and a.top < b.bottom and b.top < a.bottom


def contains(a: Rect, x: int, y: int) -> bool:
    return a.left <= x < a.right and a.top <= y < a.bottom


def host_score(rect: Rect, ex_style: int, placement: PetPlacement | None) -> int | None:
    """Score pet-host candidates, tolerating full-height/wide Chromium overlays.

    Never identify the normal, opaque Codex main window as the pet.
    """
    if not 70 <= rect.width <= 6000 or not 70 <= rect.height <= 3500:
        return None
    layered = bool(ex_style & 0x00080000)
    tool = bool(ex_style & 0x00000080)
    if not (layered or tool):
        return None
    score = 20 * int(layered) + 10 * int(tool)
    if ex_style & 0x00000008:
        score += 5
    if placement is not None:
        expected = placement.window
        sprite = placement.mascot
        if not (intersects(rect, expected)
                or contains(rect, sprite.left, sprite.top)
                or contains(rect, sprite.left + sprite.width // 2, sprite.top + sprite.height // 2)):
            return None
        score += 20
        if (abs(rect.left - expected.left) <= 64
                and abs(rect.top - expected.top) <= 64
                and abs(rect.width - expected.width) <= 64
                and abs(rect.height - expected.height) <= 64):
            score += 70
        if contains(rect, sprite.left + sprite.width // 2, sprite.top + sprite.height // 2):
            score += 40
        if contains(rect, expected.left, expected.top):
            score += 20
        # Prefer the smallest matching overlay, not an unrelated large window.
        score -= min(35, rect.width * rect.height // 100000)
    else:
        # Conservative fallback when Codex does not provide UI placement.
        if not (layered and tool):
            return None
        score -= rect.width * rect.height // 100000
    return score


def sprite_from_host(host: Rect, placement: PetPlacement | None) -> tuple[Rect, bool, str]:
    if placement is not None:
        expected = placement.window
        sprite = placement.mascot
        # The exact geometry may move with the HWND while the persisted state
        # lags behind. Apply relative mascot offsets to the actual host.
        matching = (
            abs(host.left - expected.left) <= 64
            and abs(host.top - expected.top) <= 64
            and abs(host.width - expected.width) <= 64
            and abs(host.height - expected.height) <= 64
        )
        if matching:
            dx, dy = host.left - expected.left, host.top - expected.top
            rect = Rect(sprite.left + dx, sprite.top + dy, sprite.right + dx, sprite.bottom + dy)
            return rect, placement.has_mascot_geometry, "live-host+state-mascot"
        # New Codex hosts can be full-height/full-width windows; their bounds
        # aren't the avatar. The persisted avatar point is the useful anchor.
        if contains(host, sprite.left + sprite.width // 2, sprite.top + sprite.height // 2):
            return sprite, placement.has_mascot_geometry, "state-mascot-in-large-host"
        if contains(host, expected.left, expected.top):
            return sprite, False, "state-origin-in-large-host"
    # No reliable sprite geometry: report approximate, never claim accuracy.
    width, height = 138, 155
    x = host.right - width - 32
    y = host.bottom - height - 24
    return Rect(x, y, x + width, y + height), False, "approximate-host-corner"


class PetLocator:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows is required for native Codex Pet tracking")
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.dwm = ctypes.windll.dwmapi
        self._last_lookup_at = 0.0
        self._last_pet: Pet | None = None
        self._uia = UIAMascotWatcher()
        self.proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def sig(func, argtypes, restype):
            func.argtypes = argtypes
            func.restype = restype
        sig(self.user32.EnumWindows, (self.proc_type, wintypes.LPARAM), wintypes.BOOL)
        sig(self.user32.IsWindowVisible, (wintypes.HWND,), wintypes.BOOL)
        sig(self.user32.IsIconic, (wintypes.HWND,), wintypes.BOOL)
        sig(self.user32.GetWindowRect, (wintypes.HWND, ctypes.POINTER(_RECT)), wintypes.BOOL)
        sig(self.user32.GetWindowThreadProcessId, (wintypes.HWND, ctypes.POINTER(wintypes.DWORD)), wintypes.DWORD)
        sig(self.user32.GetClassNameW, (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int), ctypes.c_int)
        sig(self.dwm.DwmGetWindowAttribute, (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD), ctypes.c_long)
        sig(self.user32.MonitorFromWindow, (wintypes.HWND, wintypes.DWORD), wintypes.HMONITOR)
        sig(self.user32.MonitorFromPoint, (wintypes.POINT, wintypes.DWORD), wintypes.HMONITOR)
        sig(self.user32.GetMonitorInfoW, (wintypes.HMONITOR, ctypes.POINTER(_MONITORINFO)), wintypes.BOOL)
        sig(self.kernel32.OpenProcess, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
        sig(self.kernel32.QueryFullProcessImageNameW, (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ), wintypes.BOOL)
        sig(self.kernel32.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL)
        get_long = self.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.user32.GetWindowLongW
        sig(get_long, (wintypes.HWND, ctypes.c_int), ctypes.c_ssize_t)
        self.get_long = get_long
        try:
            sig(self.user32.GetDpiForWindow, (wintypes.HWND,), wintypes.UINT)
        except AttributeError:
            pass

    def _process_name(self, hwnd) -> str:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = self.kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if self.kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(length)):
                return os.path.basename(buffer.value).lower()
            return ""
        finally:
            self.kernel32.CloseHandle(process)

    def _window_rect(self, hwnd) -> Rect | None:
        raw = _RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(raw)):
            return None
        return Rect(raw.left, raw.top, raw.right, raw.bottom)

    def _work_area(self, hwnd, sprite: Rect | None = None) -> Rect:
        # A full-height transparent host can straddle displays. The monitor
        # containing the actual *sprite* is the one that should clamp the HUD.
        if sprite is not None:
            center = wintypes.POINT((sprite.left + sprite.right) // 2, (sprite.top + sprite.bottom) // 2)
            monitor = self.user32.MonitorFromPoint(center, 2)
        else:
            monitor = self.user32.MonitorFromWindow(hwnd, 2)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if monitor and self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return Rect(r.left, r.top, r.right, r.bottom)
        return Rect(0, 0, self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1))

    def _dpi(self, hwnd) -> int:
        try:
            return int(self.user32.GetDpiForWindow(hwnd)) or 96
        except (AttributeError, OSError):
            return 96

    def inspect(self, *, diagnostic: bool = False) -> tuple[Pet | None, dict]:
        placement = read_pet_placement()
        diagnostics: dict = {
            "state_open_with_bounds": placement is not None,
            "state_window": placement.window.__dict__ if placement is not None else None,
            "state_mascot": placement.mascot.__dict__ if placement is not None else None,
            "mascot_geometry_available": placement.has_mascot_geometry if placement is not None else False,
            "candidates": [],
        }
        matches: list[tuple[int, int, Rect, str]] = []
        @self.proc_type
        def cb(hwnd, _unused):
            if not self.user32.IsWindowVisible(hwnd) or self.user32.IsIconic(hwnd):
                return True
            cloaked = wintypes.DWORD()
            if self.dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
                return True
            process = self._process_name(hwnd)
            if process not in ("chatgpt.exe", "codex.exe", "openai.codex.exe"):
                return True
            rect = self._window_rect(hwnd)
            if rect is None:
                return True
            ex = int(self.get_long(hwnd, -20))
            score = host_score(rect, ex, placement)
            if diagnostic:
                cls = ctypes.create_unicode_buffer(100)
                self.user32.GetClassNameW(hwnd, cls, len(cls))
                diagnostics["candidates"].append({
                    "hwnd": int(hwnd), "rect": rect.__dict__, "process": process,
                    "class_name": cls.value,
                    "ex_style_hex": hex(ex & 0xffffffff),
                    "score": score,
                })
            if score is not None:
                matches.append((score, int(hwnd), rect, process))
            return True
        self.user32.EnumWindows(cb, 0)
        if not matches:
            return None, diagnostics
        matches.sort(reverse=True)
        score, handle, host, process = matches[0]
        sprite, precise, source = sprite_from_host(host, placement)
        uia_rect = self._uia.get(handle)
        if uia_rect is not None:
            sprite, precise, source = uia_rect, True, "uia-image"
        pet = Pet(
            handle=handle, rect=sprite, host_rect=host,
            work_area=self._work_area(handle, sprite), dpi=self._dpi(handle),
            process=process, precise=precise, source=source,
        )
        diagnostics["uia_image_available"] = uia_rect is not None
        diagnostics["uia_mascot_rect"] = uia_rect.__dict__ if uia_rect else None
        return pet, diagnostics

    def close(self) -> None:
        self._uia.close()

    def find(self) -> Pet | None:
        # Parsing a potentially large global-state JSON and enumerating all
        # Chromium windows every 100ms can make Tk render sluggish. Scan at
        # roughly 4Hz; drag suppression still runs at the UI tick rate.
        now = time.monotonic()
        if now - self._last_lookup_at < 0.25:
            return self._last_pet
        pet, _ = self.inspect()
        self._last_pet = pet
        self._last_lookup_at = now
        return pet


if os.name == "nt":
    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG), ("top", wintypes.LONG),
            ("right", wintypes.LONG), ("bottom", wintypes.LONG),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
            ("rcWork", _RECT), ("dwFlags", wintypes.DWORD),
        ]
