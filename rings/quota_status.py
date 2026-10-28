"""Present Codex quota connectivity without confusing cached values for new data.

This module intentionally contains no GUI or network code.
"""
from __future__ import annotations

from datetime import datetime


def retry_delay_ms(consecutive_failures: int) -> int:
    """Retry a transient error gently; settle to the normal 60-second poll."""
    if consecutive_failures <= 0:
        return 60_000
    return min(60_000, 15_000 * (2 ** min(consecutive_failures - 1, 2)))


def brief_error(detail: str) -> str:
    text = detail.lower()
    if any(phrase in text for phrase in (
        "failed to fetch", "error sending request", "connection refused",
        "connection reset", "network", "dns", "proxy", "connect error",
    )):
        return "额度服务暂时连接失败"
    if any(phrase in text for phrase in ("timeout", "timed out", "超时")):
        return "额度查询超时"
    if any(phrase in text for phrase in ("unauthorized", "authentication", "401", "未登录")):
        return "额度查询认证失败"
    if "429" in text or "rate limit" in text:
        return "额度查询暂时受限"
    return "额度查询失败"


def format_refresh_status(
    *, last_success_wall: float | None, consecutive_failures: int,
    error: str = "", demo: bool = False, now_wall: float | None = None,
) -> str:
    """A cached gauge must never claim to be freshly updated after a failure."""
    if demo:
        return "演示数据"
    if last_success_wall is None:
        if consecutive_failures:
            return f"{brief_error(error)} · 暂无有效数据"
        return "正在查询额度"
    clock = datetime.fromtimestamp(last_success_wall).strftime("%H:%M:%S")
    if consecutive_failures:
        return f"{brief_error(error)} · 显示 {clock} 的缓存"
    return f"额度已刷新 · {clock}"
