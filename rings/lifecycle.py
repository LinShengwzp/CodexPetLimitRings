"""User-invoked Windows lifecycle controls for the independent rings app.

Only runs our bundled scripts, never kills unrelated processes or edits Codex.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
AUTOSTART_SCRIPT = ROOT / "scripts" / "Autostart.ps1"
RESTART_SCRIPT = ROOT / "scripts" / "Restart.ps1"
MAIN = ROOT / "main.py"


def python_gui_executable(executable: str | None = None) -> str:
    """Use the same interpreter/conda environment, preferring pythonw.exe."""
    current = Path(executable or sys.executable)
    if current.name.lower() in ("python.exe", "pythonw.exe"):
        quiet = current.with_name("pythonw.exe")
        if quiet.is_file():
            return str(quiet)
    return str(current)


def autostart_command(mode: str) -> list[str]:
    if mode not in {"Install", "Remove", "Status"}:
        raise ValueError("Unknown autostart action")
    return [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(AUTOSTART_SCRIPT),
        "-Mode", mode,
    ]


def restart_command(pid: int, executable: str | None = None) -> list[str]:
    if pid <= 0:
        raise ValueError("Invalid process ID")
    return [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
        "-File", str(RESTART_SCRIPT),
        "-WaitPid", str(pid),
        "-PythonPath", python_gui_executable(executable),
        "-MainPath", str(MAIN),
    ]


def hidden_creation_flags() -> int:
    return getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
