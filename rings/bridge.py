"""Read Codex subscription quotas through the official local App Server protocol.

No credentials are read, stored or transmitted by this program.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .core import Quotas, parse_quotas


class QuotaReadError(RuntimeError):
    pass


def _command_for(path: Path) -> list[str]:
    if path.suffix.lower() in (".cmd", ".bat"):
        return [os.environ.get("ComSpec", "cmd.exe"), "/d", "/c", str(path), "app-server", "--stdio"]
    return [str(path), "app-server", "--stdio"]


def codex_command() -> list[str]:
    """Prefer the bundled Desktop native executable; support an explicit override."""
    override = os.environ.get("CODEX_PET_CODEX_BIN")
    if override:
        executable = Path(os.path.expandvars(os.path.expanduser(override)))
        if not executable.is_file():
            raise QuotaReadError("CODEX_PET_CODEX_BIN 指向的文件不存在")
        return _command_for(executable)

    local_app = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    bin_dir = local_app / "OpenAI" / "Codex" / "bin"
    bundled = sorted(bin_dir.glob("*/codex.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
    if bundled:
        return _command_for(bundled[0])

    for name in ("codex.exe", "codex.cmd", "codex"):
        found = shutil.which(name)
        if found:
            return _command_for(Path(found))
    raise QuotaReadError("找不到 Codex CLI；请先安装或设置 CODEX_PET_CODEX_BIN")


def _reader(stream, output: queue.Queue):
    try:
        for line in stream:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and isinstance(message.get("id"), int):
                output.put(message)
    except (OSError, UnicodeError):
        pass


def read_quotas(timeout: float = 12.0) -> Quotas:
    """Execute two read-only JSON-RPC requests; enforce an overall timeout.

    Starts a short-lived App Server process in a background caller thread.
    The parent GUI never waits for network I/O.
    """
    command = codex_command()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
    except OSError as exc:
        raise QuotaReadError(f"无法启动 Codex App Server：{exc}") from exc

    incoming: queue.Queue = queue.Queue()
    deadline = time.monotonic() + timeout
    try:
        if process.stdout is None or process.stdin is None:
            raise QuotaReadError("Codex App Server 管道不可用")
        thread = threading.Thread(target=_reader, args=(process.stdout, incoming), daemon=True)
        thread.start()

        def send(message: dict) -> None:
            try:
                assert process.stdin is not None
                process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise QuotaReadError("Codex App Server 已断开") from exc

        def wait_for(request_id: int) -> Any:
            while time.monotonic() < deadline:
                try:
                    reply = incoming.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    if process.poll() is not None:
                        raise QuotaReadError("Codex App Server 在响应前退出")
                    continue
                if reply.get("id") != request_id:
                    continue
                if reply.get("error") is not None:
                    error = reply["error"]
                    info = error.get("message", "unknown") if isinstance(error, dict) else str(error)
                    # A transport failure is not an explicit permission
                    # rejection. Preserve the upstream detail for diagnostics.
                    if any(term in info.lower() for term in (
                        "failed to fetch", "error sending request",
                        "connection", "network", "timeout",
                    )):
                        raise QuotaReadError(f"Codex 额度服务请求失败：{info[:240]}")
                    raise QuotaReadError(f"Codex 返回额度查询错误：{info[:240]}")
                return reply.get("result")
            raise QuotaReadError("Codex App Server 额度查询超时")

        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "codex_pet_limit_rings", "title": "Pet Limit Rings", "version": "0.1.0"},
            "capabilities": {},
        }})
        wait_for(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/rateLimits/read", "params": {}})
        data = wait_for(2)
        try:
            return parse_quotas(data)
        except ValueError as exc:
            raise QuotaReadError(str(exc)) from exc
    finally:
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            if process.stdout:
                process.stdout.close()
        except OSError:
            pass
