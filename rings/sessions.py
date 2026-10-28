"""Opt-in, local Codex JSONL token accounting for per-model statistics.

We read ONLY envelope types/usage fields. We never persist conversation
messages, prompts, tools, tool outputs, auth tokens or file contents.

Unlike rate-limit percentages these counts are tokens from *local sessions*
only. They cannot be assigned a percent of subscription quota.
"""
from __future__ import annotations

import json
from contextlib import closing
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .history import connect


UNKNOWN = "未识别模型"
FIELDS = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")


def session_root() -> Path:
    return Path(os.path.expandvars(os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex")))) / "sessions"


def _timestamp(raw, fallback: int) -> int:
    if not isinstance(raw, str):
        return fallback
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError, OverflowError):
        return fallback


def _counts(obj: dict | None) -> dict | None:
    if not isinstance(obj, dict):
        return None
    result = {}
    for key in FIELDS:
        value = obj.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return None
        result[key] = int(value)
    return result


def _model_name(payload: dict) -> str | None:
    raw = payload.get("model")
    if isinstance(raw, str) and 0 < len(raw) <= 100:
        return raw
    return None


def parse_session_lines(lines, state: dict, *, start_offset: int = 0, fallback_ts: int = 0):
    """Return deduplicated usage events plus resumable session state.

    Each iterable item is (byte_offset, JSONL line). The offset is end-of-line.
    Ignore partial/incomplete lines (handled by reader), repeated cumulative
    snapshots, and non-usage envelopes. Session model switches come from
    turn_context; never infer attribution from a quota bucket.
    """
    model = state.get("current_model") or UNKNOWN
    previous = {k: state.get("last_" + k.split("_tokens")[0]) for k in FIELDS}
    events = []
    for offset, line in lines:
        try:
            entry = json.loads(line)
        except (UnicodeError, ValueError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        if entry.get("type") == "turn_context":
            model = _model_name(payload) or model
            continue
        if entry.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if not isinstance(info, dict):
            continue
        cumulative = _counts(info.get("total_token_usage"))
        last = _counts(info.get("last_token_usage"))
        if cumulative is None and last is None:
            continue
        if cumulative is not None:
            if all(previous.get(k) is not None for k in FIELDS):
                # An unchanged cumulative snapshot is a status event, not
                # another model call. Compaction may reset the counter.
                if all(cumulative[k] == previous[k] for k in FIELDS):
                    continue
                if all(cumulative[k] >= previous[k] for k in FIELDS):
                    delta = {k: cumulative[k] - previous[k] for k in FIELDS}
                else:
                    delta = last if last is not None else {k: 0 for k in FIELDS}
            else:
                delta = cumulative
            previous = cumulative
        else:
            delta = last
        if not delta["input_tokens"] and not delta["output_tokens"]:
            continue
        ts = _timestamp(entry.get("timestamp"), fallback_ts)
        events.append((offset, ts, model, *(delta[k] for k in FIELDS)))
    new_state = {"current_model": model}
    for k in FIELDS:
        new_state["last_" + k.split("_tokens")[0]] = previous.get(k)
    return events, new_state


def _cursor_state(row) -> dict:
    if row is None:
        return {}
    return {
        "current_model": row[3],
        "last_input": row[5], "last_output": row[6],
        "last_cached_input": row[7], "last_reasoning_output": row[8],
    }


def import_sessions(*, db_path: Path | None = None, root: Path | None = None,
                    days: int = 60, max_bytes: int = 48_000_000,
                    max_files: int = 500) -> dict:
    """Incremental bounded import. Runs only in a statistics worker thread.

    On first use scans recent local sessions, then resumes by byte offset.
    Files > 32MB are skipped rather than stalling the entire desktop app.
    Partial trailing records are left for the next refresh.
    """
    root = root if root is not None else session_root()
    result = {"files": 0, "new_events": 0, "bytes": 0, "skipped_large": 0,
              "error": None, "source": str(root)}
    if not root.exists():
        return result
    cutoff = time.time() - min(365, max(1, days)) * 86400
    candidates = []
    try:
        for directory, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".jsonl"):
                    continue
                p = Path(directory) / name
                try:
                    stat = p.stat()
                    if stat.st_mtime >= cutoff:
                        candidates.append((stat.st_mtime_ns, p, stat))
                except OSError:
                    continue
    except OSError as exc:
        result["error"] = str(exc)
        return result

    # Newest file first ensures recent activity appears even with a byte cap.
    candidates.sort(reverse=True, key=lambda x: x[0])
    budget = max_bytes
    with closing(connect(db_path)) as db:
        for _, file, stat in candidates[:max_files]:
            if stat.st_size > 32_000_000:
                result["skipped_large"] += 1
                continue
            path_key = str(file)
            row = db.execute(
                "SELECT path,byte_offset,size,current_model,last_total,last_input,"
                "last_output,last_cached,last_reasoning FROM session_cursors WHERE path=?",
                (path_key,),
            ).fetchone()
            offset = row[1] if row is not None and stat.st_size >= row[1] else 0
            pending = stat.st_size - offset
            if pending <= 0:
                continue
            if pending > budget:
                # Files are scanned from beginning to end, by a bounded
                # chunk, but do not attempt a multi-GB transcript.
                pending = budget
            if pending <= 0:
                break
            try:
                with file.open("rb") as stream:
                    stream.seek(offset)
                    blob = stream.read(pending)
            except OSError:
                continue
            newline = blob.rfind(b"\n")
            if newline < 0:
                continue
            chunk = blob[:newline + 1]
            pairs = []
            cursor = offset
            for line in chunk.splitlines(keepends=True):
                cursor += len(line)
                pairs.append((cursor, line.decode("utf-8", errors="replace")))
            start_state = _cursor_state(row) if offset > 0 else {}
            events, end_state = parse_session_lines(
                pairs, start_state, start_offset=offset, fallback_ts=int(stat.st_mtime),
            )
            db.executemany(
                "INSERT OR IGNORE INTO token_events"
                "(path,byte_offset,ts,model,input_tokens,output_tokens,"
                "cached_input_tokens,reasoning_output_tokens)"
                " VALUES(?,?,?,?,?,?,?,?)",
                [(path_key, *row) for row in events],
            )
            db.execute(
                "INSERT OR REPLACE INTO session_cursors"
                "(path,byte_offset,size,mtime_ns,current_model,last_total,last_input,"
                "last_output,last_cached,last_reasoning) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (path_key, cursor, stat.st_size, stat.st_mtime_ns,
                 end_state.get("current_model", UNKNOWN), None,
                 end_state.get("last_input"), end_state.get("last_output"),
                 end_state.get("last_cached_input"), end_state.get("last_reasoning_output")),
            )
            result["files"] += 1
            result["new_events"] += len(events)
            result["bytes"] += len(chunk)
            budget -= len(chunk)
            if budget <= 0:
                break
        db.commit()
    return result
