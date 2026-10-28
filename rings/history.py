"""Local, account-free history of the Codex subscription quota gauges.

Quota usage is NOT tokens or money. We persist percent-remaining snapshots
and calculate *observed* positive percentage-point changes only inside the
same reset epoch. No auth, prompts, model outputs or network payloads stored.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .calibration import settings_path
from .core import Quota, Quotas


def database_path() -> Path:
    return settings_path().parent / "usage-history.sqlite3"


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path if path is not None else database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(target), timeout=5)
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("""
        CREATE TABLE IF NOT EXISTS quota_samples(
            ts INTEGER NOT NULL,
            window TEXT NOT NULL CHECK(window IN ('5h', '7d')),
            remaining INTEGER NOT NULL CHECK(remaining BETWEEN 0 AND 100),
            resets_at INTEGER NOT NULL,
            PRIMARY KEY(ts, window)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_quota_window_time ON quota_samples(window,ts)")
    db.execute("""
        CREATE TABLE IF NOT EXISTS session_cursors(
            path TEXT PRIMARY KEY,
            byte_offset INTEGER NOT NULL,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            current_model TEXT NOT NULL DEFAULT '',
            last_total INTEGER,
            last_input INTEGER,
            last_output INTEGER,
            last_cached INTEGER,
            last_reasoning INTEGER
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS token_events(
            path TEXT NOT NULL, byte_offset INTEGER NOT NULL,
            ts INTEGER NOT NULL, model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            cached_input_tokens INTEGER NOT NULL, reasoning_output_tokens INTEGER NOT NULL,
            PRIMARY KEY(path, byte_offset)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_token_ts ON token_events(ts)")
    db.commit()
    return db


def store_quotas(quotas: Quotas, *, ts: int | None = None, path: Path | None = None) -> int:
    now = int(time.time() if ts is None else ts)
    rows = []
    for label, quota in (("5h", quotas.five_hour), ("7d", quotas.weekly)):
        if quota.remaining is None or quota.resets_at is None:
            continue
        if not 0 <= quota.remaining <= 100 or quota.resets_at < 1:
            continue
        rows.append((now, label, quota.remaining, quota.resets_at))
    if not rows:
        return 0
    with closing(connect(path)) as db:
        db.executemany(
            "INSERT OR REPLACE INTO quota_samples(ts,window,remaining,resets_at) VALUES(?,?,?,?)",
            rows,
        )
        db.commit()
    return len(rows)


def quota_history(
    window: str, since: int, *, until: int | None = None, path: Path | None = None,
) -> list[dict]:
    if window not in ("5h", "7d"):
        raise ValueError("Unsupported quota window")
    end = int(time.time()) if until is None else until
    with closing(connect(path)) as db:
        preceding = db.execute(
            "SELECT ts,remaining,resets_at FROM quota_samples "
            "WHERE window=? AND ts<? ORDER BY ts DESC LIMIT 1", (window, since),
        ).fetchone()
        rows = db.execute(
            "SELECT ts,remaining,resets_at FROM quota_samples "
            "WHERE window=? AND ts>=? AND ts<=? ORDER BY ts",
            (window, since, end),
        ).fetchall()
    result = []
    previous = preceding
    for ts, remaining, reset in rows:
        # First sample is a baseline, never a guessed consumption event.
        delta = 0
        if previous is not None and previous[2] == reset:
            delta = max(0, previous[1] - remaining)
        result.append({
            "ts": ts, "remaining": remaining, "resets_at": reset,
            "observed_spent_pp": delta,
        })
        previous = (ts, remaining, reset)
    return result


def quota_summary(since: int, *, until: int | None = None, path: Path | None = None) -> dict:
    result = {}
    for name in ("5h", "7d"):
        series = quota_history(name, since, until=until, path=path)
        result[name] = {
            "observed_spent_pp": sum(row["observed_spent_pp"] for row in series),
            "sample_count": len(series),
            "last_remaining": series[-1]["remaining"] if series else None,
            "first_ts": series[0]["ts"] if series else None,
            "last_ts": series[-1]["ts"] if series else None,
            "series": series,
        }
    return result


def token_summary(since: int, *, until: int | None = None, path: Path | None = None) -> dict:
    end = int(time.time()) if until is None else until
    with closing(connect(path)) as db:
        rows = db.execute(
            "SELECT model, SUM(input_tokens), SUM(output_tokens), "
            "SUM(cached_input_tokens), SUM(reasoning_output_tokens), COUNT(*) "
            "FROM token_events WHERE ts>=? AND ts<=? GROUP BY model "
            "ORDER BY SUM(input_tokens+output_tokens) DESC",
            (since, end),
        ).fetchall()
        daily = db.execute(
            "SELECT strftime('%Y-%m-%d', ts, 'unixepoch', 'localtime'), "
            "SUM(input_tokens), SUM(output_tokens) "
            "FROM token_events WHERE ts>=? AND ts<=? GROUP BY 1 ORDER BY 1",
            (since, end),
        ).fetchall()
    models = [
        {
            "model": model, "input": int(ipt), "output": int(out),
            "cached": int(cached), "reasoning": int(reason),
            "events": int(count),
        }
        for model, ipt, out, cached, reason, count in rows
    ]
    return {
        "models": models,
        "daily": [{"date": day, "input": i, "output": o} for day, i, o in daily],
        "total_tokens": sum(row["input"] + row["output"] for row in models),
    }


def collect_history(days: int, *, path: Path | None = None, now: int | None = None) -> dict:
    timestamp = int(time.time() if now is None else now)
    since = timestamp - min(365, max(1, int(days))) * 86400
    return {
        "since": since,
        "until": timestamp,
        "quotas": quota_summary(since, until=timestamp, path=path),
        "tokens": token_summary(since, until=timestamp, path=path),
    }
