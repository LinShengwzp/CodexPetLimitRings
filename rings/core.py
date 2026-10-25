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
    right_x = pet.right + margin
    left_x = pet.left - width - margin
    base_x = right_x if right_x + width <= work.right else left_x
    base_y = pet.top + max(0, (pet.height - height) // 2)
    max_x = max(work.left, work.right - width)
    max_y = max(work.top, work.bottom - height)
    x = max(work.left, min(max_x, base_x + offset_x))
    y = max(work.top, min(max_y, base_y + offset_y))
    return x, y


def explain(quotas: Quotas) -> dict:
    def row(q: Quota) -> dict:
        return {"remaining_percent": q.remaining, "resets_at": q.resets_at}
    return {"five_hour": row(quotas.five_hour), "weekly": row(quotas.weekly)}
