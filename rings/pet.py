"""Find the *native* Codex Mini / Pet HWND and its monitor work area on Windows."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

from .core import Rect


@dataclass(frozen=True)
class Pet:
    handle: int
    rect: Rect
    work_area: Rect
    dpi: int
    process: str


class PetLocator:
    """Only trust visible, non-cloaked, layered tool windows owned by Codex.

    The overlay itself is owned by pythonw.exe, so it cannot match this filter.
    """
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows is required for native Codex Pet window tracking")
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.dwm = ctypes.windll.dwmapi
        self.proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = (self.proc_type, wintypes.LPARAM)
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = (wintypes.HWND,)
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self.dwm.DwmGetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        self.dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        self.user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
        self.user32.GetDpiForWindow.restype = wintypes.UINT
        self.user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(_RECT))
        self.user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self.user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
        self.user32.MonitorFromWindow.restype = wintypes.HMONITOR
        self.user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(_MONITORINFO))
        self.kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        self.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        long_proc = self.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.user32.GetWindowLongW
        long_proc.argtypes = (wintypes.HWND, ctypes.c_int)
        long_proc.restype = ctypes.c_ssize_t
        self.get_long = long_proc
        self._cached: int | None = None

    def _process_name(self, handle) -> str:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        process = self.kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if self.kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return os.path.basename(buffer.value).lower()
        finally:
            self.kernel32.CloseHandle(process)
        return ""

    def _rect(self, handle) -> Rect | None:
        raw = _RECT()
        if not self.user32.GetWindowRect(handle, ctypes.byref(raw)):
            return None
        return Rect(raw.left, raw.top, raw.right, raw.bottom)

    def _work_area(self, handle) -> Rect:
        monitor = self.user32.MonitorFromWindow(handle, 2)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if monitor and self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return Rect(r.left, r.top, r.right, r.bottom)
        return Rect(0, 0, self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1))

    def _dpi(self, handle) -> int:
        try:
            return int(self.user32.GetDpiForWindow(handle)) or 96
        except (AttributeError, OSError):
            return 96

    def _candidate(self, hwnd: int) -> tuple[int, Pet] | None:
        if not self.user32.IsWindowVisible(hwnd) or self.user32.IsIconic(hwnd):
            return None
        rect = self._rect(hwnd)
        if rect is None or not 110 <= rect.width <= 1400 or not 110 <= rect.height <= 1400:
            return None
        ex_style = int(self.get_long(hwnd, -20))
        # Electron/Chromium desktop pet is a small transparent tool window.
        if ex_style & 0x00080000 == 0 or ex_style & 0x00000080 == 0:
            return None
        cloaked = wintypes.DWORD()
        if self.dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
            return None
        name = self._process_name(hwnd)
        if name not in ("codex.exe", "chatgpt.exe", "openai.codex.exe"):
            return None
        cls = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, cls, len(cls))
        score = 100
        if cls.value == "Chrome_WidgetWin_1":
            score += 30
        if ex_style & 0x8:  # topmost
            score += 20
        if ex_style & 0x20:  # click-through
            score += 5
        # A main window can never pass the toolwindow+layered combination, but
        # prefer compact pet overlays if several such windows are available.
        if rect.width < 800 and rect.height < 800:
            score += 15
        score -= (rect.width * rect.height) // 45000
        return score, Pet(int(hwnd), rect, self._work_area(hwnd), self._dpi(hwnd), name)

    def find(self) -> Pet | None:
        if self._cached:
            hit = self._candidate(self._cached)
            if hit:
                return hit[1]
            self._cached = None

        matches: list[tuple[int, Pet]] = []

        @self.proc_type
        def callback(hwnd, _parameter):
            hit = self._candidate(hwnd)
            if hit is not None:
                matches.append(hit)
            return True

        self.user32.EnumWindows(callback, 0)
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        pet = matches[0][1]
        self._cached = pet.handle
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
