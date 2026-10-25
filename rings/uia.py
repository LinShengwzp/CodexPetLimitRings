"""Asynchronous bridge to a persistent Windows UI Automation child process.

The child reads only the image bounds (not the page text). A separate
PowerShell 5.1 STA process avoids blocking Tk's GUI thread on Chromium UIA.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from .core import Rect


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "PetUiaWatcher.ps1"


def parse_uia_line(line: str, expected_hwnd: int) -> Rect | None:
    try:
        message = json.loads(line)
        if not isinstance(message, dict) or message.get("status") != "ok":
            return None
        if int(message.get("hwnd", -1)) != expected_hwnd:
            return None
        coordinates = []
        for key in ("left", "top", "right", "bottom"):
            v = message.get(key)
            if isinstance(v, bool) or not isinstance(v, int) or abs(v) >= 100000:
                return None
            coordinates.append(v)
        box = Rect(*coordinates)
        if 40 <= box.width <= 800 and 40 <= box.height <= 800:
            return box
    except (ValueError, TypeError, OverflowError, json.JSONDecodeError):
        pass
    return None


class UIAMascotWatcher:
    def __init__(self, *, fresh_seconds: float = 1.8):
        self.fresh_seconds = fresh_seconds
        self._process: subprocess.Popen | None = None
        self._hwnd: int | None = None
        self._last_box: Rect | None = None
        self._last_update: float = 0.0
        self._restart_after: float = 0.0
        self._lock = threading.Lock()
        atexit.register(self.close)

    def _read_output(self, process: subprocess.Popen, hwnd: int):
        try:
            if process.stdout is None:
                return
            for line in process.stdout:
                box = parse_uia_line(line, hwnd)
                with self._lock:
                    if process is not self._process or self._hwnd != hwnd:
                        break
                    # A not_found result invalidates previous position; do
                    # not continue rendering at the old sprite coordinates.
                    self._last_box = box
                    self._last_update = time.monotonic()
        except (OSError, UnicodeError):
            pass

    def _stop(self) -> None:
        proc = self._process
        self._process = None
        self._hwnd = None
        self._last_box = None
        self._last_update = 0.0
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        # Avoid waiting synchronously for any slow UIA call.
        try:
            if proc.stdout:
                proc.stdout.close()
        except OSError:
            pass

    def close(self) -> None:
        with self._lock:
            self._stop()

    def _start(self, hwnd: int) -> None:
        if os.name != "nt" or not SCRIPT.is_file():
            return
        command = [
            "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
            "-HostHwnd", str(hwnd), "-IntervalMs", "300",
        ]
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._hwnd = hwnd
            reader = threading.Thread(
                target=self._read_output, args=(self._process, hwnd),
                daemon=True, name="codex-pet-uia-reader",
            )
            reader.start()
        except OSError:
            self._process = None
            self._hwnd = None

    def get(self, hwnd: int) -> Rect | None:
        """Return fresh mascot bounds immediately, or None while starting."""
        with self._lock:
            now = time.monotonic()
            if (self._process is not None
                    and (self._hwnd != hwnd or self._process.poll() is not None)):
                self._stop()
                self._restart_after = now + 0.5
            if self._process is None and now >= self._restart_after:
                self._start(hwnd)
                if self._process is None:
                    self._restart_after = now + 5.0
            if self._hwnd != hwnd or now - self._last_update > self.fresh_seconds:
                return None
            return self._last_box
