"""Opt-in, rate-limited JSONL tracing of Codex Pet / ring screen coordinates.

Only Win32 geometry and simple UI state are recorded. Never log the Codex
global state contents, credentials, account data, titles, or prompts.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def default_log_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "logs"


def make_position_tracer(
    *,
    interval: float = 0.5,
    directory: Path | None = None,
    console: bool = True,
) -> "PositionTracer":
    folder = directory if directory is not None else default_log_directory()
    folder.mkdir(parents=True, exist_ok=True)
    log_file = folder / ("positions-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".jsonl")
    logger = logging.getLogger("codexpet.positions")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # CLI creates only one instance; defensively close existing handlers.
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    if console:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream)
    return PositionTracer(logger=logger, file_path=log_file, interval=interval)


class PositionTracer:
    def __init__(
        self,
        *,
        logger: Any,
        file_path: Path | None = None,
        interval: float = 0.5,
    ):
        self.logger = logger
        self.file_path = file_path
        self.interval = max(0.2, float(interval))
        self._last_at: float | None = None
        self._last_state: tuple | None = None

    def emit(self, event: str, fields: dict, *, force: bool = False, now: float | None = None) -> bool:
        """Always print transitions. Throttle repeated samples on the UI thread."""
        at = time.monotonic() if now is None else now
        state = (
            event,
            fields.get("visible"),
            fields.get("reason"),
            fields.get("position_source"),
            fields.get("pet_hwnd"),
            fields.get("calibration_active"),
        )
        transition = state != self._last_state
        # Event switches need immediate inspection. Unchanged states still
        # get regular coordinate samples; holding the mouse is not special.
        if not (force or transition) and self._last_at is not None and at - self._last_at < self.interval:
            return False
        payload = {"at": datetime.now().astimezone().isoformat(timespec="milliseconds"), "event": event}
        payload.update(fields)
        self.logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))
        self._last_at = at
        self._last_state = state
        return True
