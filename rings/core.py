"""Pure data parsing and geometry; safe to test without a Windows desktop."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Quota:
    remaining: int | None = None
    resets_at: int | None = None

    def reset_label(self) -> str:
        if self.resets_at is None:
            return "重置时间未知"
        try:
            return datetime.fromtimestamp(self.resets_at).strftime("%m-%d %H:%M 重置")
        except (ValueError, OverflowError, OSError):
            return "重置时间未知"


@dataclass(frozen=True)
class Quotas:
    five_hour: Quota
    weekly: Quota


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


def _bucket_window(raw: Any) -> tuple[int, Quota] | None:
    if not isinstance(raw, dict):
        return None
    minutes = raw.get("windowDurationMins", raw.get("window_duration_mins"))
    used = raw.get("usedPercent", raw.get("used_percent"))
    if isinstance(minutes, bool) or isinstance(used, bool):
        return None
    try:
        minutes_num = int(minutes)
        used_num = float(used)
    except (TypeError, ValueError, OverflowError):
        return None
    if not 0 <= used_num <= 100:
        return None
    reset = raw.get("resetsAt", raw.get("resets_at"))
    try:
        reset_num = int(reset) if reset is not None else None
        if reset_num is not None and not 1 <= reset_num <= 253402271999:
            reset_num = None
    except (TypeError, ValueError, OverflowError):
        reset_num = None
    return minutes_num, Quota(round(100.0 - used_num), reset_num)


def parse_quotas(response: Any) -> Quotas:
    """Select the actual 300m and 10080m windows; never confuse weekly with 5h.

    This deliberately does not infer a duration from a primary/secondary slot.
    Some plans/events return other windows or only a weekly window.
    """
    if not isinstance(response, dict):
        raise ValueError("Codex did not return a rate-limit response")
    by_id = response.get("rateLimitsByLimitId", response.get("rate_limits_by_limit_id"))
    bucket = by_id.get("codex") if isinstance(by_id, dict) else None
    if not isinstance(bucket, dict):
        bucket = response.get("rateLimits", response.get("rate_limits"))
    if not isinstance(bucket, dict):
        raise ValueError("Codex subscription quota was not available")

    windows: dict[int, Quota] = {}
    for name in ("primary", "secondary"):
        parsed = _bucket_window(bucket.get(name))
        if parsed is not None:
            windows[parsed[0]] = parsed[1]

    # Other quota buckets may be present. Do not label a generic 30-day window
    # as a weekly or five-hour allowance.
    return Quotas(windows.get(300, Quota()), windows.get(10080, Quota()))


def follow_position(
    pet: Rect, width: int, height: int, work: Rect,
    offset_x: int = 0, offset_y: int = 0,
) -> tuple[int, int]:
    """Place a compact badge beside the pet, not over her face.

    Prefer the right side; flip to the left if the right side is offscreen.
    Offsets are persisted as screen-pixel adjustments relative to the pet.
    """
    margin = 8
    if pet.width >= 540 or pet.height >= 700:
        # Codex sometimes hosts the tiny avatar inside a large transparent
        # window (e.g. 888x1080). Its right edge is not the character.
        base_x = pet.left + min(220, max(50, round(pet.width * 0.24)))
        base_y = pet.bottom - height - 155
    else:
        right_x = pet.right + margin
        left_x = pet.left - width - margin
        base_x = right_x if right_x + width <= work.right else left_x
        base_y = pet.top + max(0, (pet.height - height) // 2)
    max_x = max(work.left, work.right - width)
    max_y = max(work.top, work.bottom - height)
    x = max(work.left, min(max_x, base_x + offset_x))
    y = max(work.top, min(max_y, base_y + offset_y))
    return x, y



class PetMotionTracker:
    """Hide the overlay while the native pet host window moves.

    CSS/sprite motion inside a stationary transparent HWND cannot be sensed
    using Win32 rectangles alone.
    """

    def __init__(self, settle_seconds: float = 0.55, tolerance_px: int = 1):
        self.settle_seconds = settle_seconds
        self.tolerance_px = tolerance_px
        self.last_rect: Rect | None = None
        self.last_handle: int | None = None
        self.changed_at: float | None = None

    def reset(self) -> None:
        self.last_rect = None
        self.last_handle = None
        self.changed_at = None

    def should_show(self, rect: Rect, handle: int, now: float) -> bool:
        previous = self.last_rect
        changed = (
            previous is None or self.last_handle != handle
            or max(
                abs(a - b) for a, b in zip(
                    (rect.left, rect.top, rect.right, rect.bottom),
                    (previous.left, previous.top, previous.right, previous.bottom),
                )
            ) > self.tolerance_px
        )
        if changed:
            self.last_rect = rect
            self.last_handle = handle
            self.changed_at = now
            return False
        return self.changed_at is not None and now - self.changed_at >= self.settle_seconds


def explain(quotas: Quotas) -> dict:
    def row(q: Quota) -> dict:
        return {"remaining_percent": q.remaining, "resets_at": q.resets_at}
    return {"five_hour": row(quotas.five_hour), "weekly": row(quotas.weekly)}
