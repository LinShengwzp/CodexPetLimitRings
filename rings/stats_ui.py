"""Standalone Tk dashboard: quota history + local per-model token usage.

The tiny pet HUD is deliberately unchanged. Query/import runs in a worker
thread; all Tk widgets are mutated only from Tk's main thread.
"""
from __future__ import annotations

import math
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from .history import quota_summary, token_summary, database_path
from .sessions import import_sessions


PERIODS = (
    ("近 6 小时", 6 * 3600),
    ("近 24 小时", 24 * 3600),
    ("近 7 天", 7 * 86400),
    ("近 30 天", 30 * 86400),
)


def points_for_plot(series: list[dict], width: int, left: float,
                    right: float, top: float, bottom: float, start: int,
                    end: int) -> list[list[tuple[float, float]]]:
    """Separate curves by reset timestamp so resets never draw fake trends."""
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    last_reset = None
    # One pixel column needs at most its first and last point.
    previous_pixel = None
    for row in series:
        reset = row["resets_at"]
        if last_reset is not None and reset != last_reset and current:
            segments.append(current)
            current = []
            previous_pixel = None
        last_reset = reset
        x = left + ((row["ts"] - start) / max(1, end - start)) * (right - left)
        x = max(left, min(right, x))
        y = bottom - (row["remaining"] / 100.0) * (bottom - top)
        p = (x, y)
        px = int(x)
        if previous_pixel == px and current:
            current[-1] = p
        else:
            current.append(p)
        previous_pixel = px
    if current:
        segments.append(current)
    return segments


class StatisticsWindow:
    def __init__(self, parent: tk.Misc, *, on_close=None):
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("小龙娘 · 法力消耗统计")
        self.window.geometry("820x710")
        self.window.minsize(640, 550)
        self.window.configure(bg="#f7f4fb")
        self.window.wm_attributes("-topmost", False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.pending = False
        self.channel: queue.Queue = queue.Queue()
        self.period = tk.StringVar(value=PERIODS[1][0])
        self.summary = tk.StringVar(value="读取本地统计中……")
        self.note = tk.StringVar(value="统计开始前的额度记录无法补录。模型 Token 来源于本机 Codex 会话日志。")
        self.data = None

        bar = ttk.Frame(self.window, padding=(15, 14, 15, 6))
        bar.pack(fill="x")
        ttk.Label(bar, text="法力账本", font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        self.selector = ttk.Combobox(
            bar, textvariable=self.period, values=[label for label, _ in PERIODS],
            state="readonly", width=13,
        )
        self.selector.pack(side="right", padx=(6, 0))
        self.selector.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="刷新", command=self.refresh).pack(side="right", padx=6)
        ttk.Label(self.window, textvariable=self.summary, padding=(16, 4, 16, 8),
                  font=("Microsoft YaHei UI", 10)).pack(fill="x")

        group = ttk.LabelFrame(self.window, text="订阅额度剩余比例（%）", padding=6)
        group.pack(fill="x", padx=15, pady=(0, 12))
        self.chart = tk.Canvas(group, bg="#ffffff", height=248, highlightthickness=0)
        self.chart.pack(fill="x", expand=True)
        self.chart.bind("<Configure>", lambda _event: self._draw_chart())

        group2 = ttk.LabelFrame(self.window, text="本地会话 Token 用量（按模型）", padding=6)
        group2.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        columns = ("model", "input", "output", "cached", "total")
        self.tree = ttk.Treeview(group2, columns=columns, show="headings", height=7)
        headers = [
            ("model", "模型", 200),
            ("input", "输入 Token", 135),
            ("output", "输出 Token", 135),
            ("cached", "其中缓存输入", 130),
            ("total", "合计", 135),
        ]
        for name, label, size in headers:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=size, minwidth=100, anchor="w" if name == "model" else "e")
        scroll = ttk.Scrollbar(group2, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Label(
            self.window,
            textvariable=self.note, foreground="#777184", wraplength=760,
            padding=(15, 0, 15, 12),
        ).pack(fill="x")
        self.window.after(150, self._poll)
        self.refresh()

    def exists(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def lift(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        if self.exists():
            self.window.destroy()
        if self.on_close is not None:
            self.on_close()

    def _interval(self) -> int:
        return dict(PERIODS).get(self.period.get(), 86400)

    def refresh(self) -> None:
        if self.pending:
            return
        self.pending = True
        self.summary.set("正在统计……（首次读取本机历史会话可能稍慢）")
        seconds = self._interval()

        def work():
            try:
                # Import only bounded recent session data and no user content.
                imported = import_sessions(days=max(2, int(seconds / 86400) + 1))
                now = int(time.time())
                since = now - seconds
                result = {
                    "since": since, "until": now,
                    "quotas": quota_summary(since, until=now),
                    "tokens": token_summary(since, until=now),
                    "import": imported,
                }
                self.channel.put(("ok", result))
            except Exception as exc:
                self.channel.put(("error", str(exc)[:240]))

        threading.Thread(target=work, daemon=True, name="codex-pet-statistics").start()

    def _poll(self) -> None:
        if not self.exists():
            return
        try:
            kind, value = self.channel.get_nowait()
        except queue.Empty:
            self.window.after(150, self._poll)
            return
        self.pending = False
        if kind == "ok":
            self.data = value
            q5, q7 = value["quotas"]["5h"], value["quotas"]["7d"]
            def desc(name, row):
                return f"{name} 观测消耗 {row['observed_spent_pp']} 个百分点（{row['sample_count']} 个样本）"
            self.summary.set(desc("5h", q5) + "     " + desc("每周", q7))
            for node in self.tree.get_children():
                self.tree.delete(node)
            for row in value["tokens"]["models"]:
                total = row["input"] + row["output"]
                self.tree.insert("", "end", values=(
                    row["model"], f"{row['input']:,}", f"{row['output']:,}",
                    f"{row['cached']:,}", f"{total:,}",
                ))
            if not value["tokens"]["models"]:
                self.tree.insert("", "end", values=("暂无本地 Token 记录", "—", "—", "—", "—"))
            scanned = value["import"]
            self.note.set(
                f"本地 Token 合计：{value['tokens']['total_tokens']:,}。"
                f"本次扫描 {scanned['files']} 个更新的日志文件。"
                "缓存输入包含在输入 Token 内，不要重复相加。"
                "订阅额度百分比与 Token 无固定兑换率；跨重置与采样间隔外的消耗无法精确还原。"
                "数据仅保存在本机。"
            )
            self._draw_chart()
        else:
            self.summary.set("统计失败：" + value)
        self.window.after(150, self._poll)

    def _draw_chart(self) -> None:
        if not self.exists():
            return
        canvas = self.chart
        canvas.delete("all")
        w = max(460, canvas.winfo_width())
        h = max(210, canvas.winfo_height())
        left, right, top, bottom = 53, w - 24, 20, h - 39
        for percentage in (0, 25, 50, 75, 100):
            y = bottom - percentage / 100 * (bottom - top)
            canvas.create_line(left, y, right, y, fill="#e8e4ef")
            canvas.create_text(left - 10, y, text=str(percentage), fill="#7a7485",
                               anchor="e", font=("Segoe UI", 9))
        if self.data is None:
            canvas.create_text(w / 2, h / 2, text="暂无采样记录", fill="#777184")
            return
        start, end = self.data["since"], self.data["until"]
        for fraction in (0, .25, .5, .75, 1):
            x = left + fraction * (right - left)
            stamp = datetime.fromtimestamp(start + (end - start) * fraction)
            fmt = "%H:%M" if end - start <= 86400 else "%m-%d"
            canvas.create_text(x, bottom + 18, text=stamp.strftime(fmt),
                               fill="#7a7485", font=("Segoe UI", 9))
        counts = 0
        for window, color in (("5h", "#9677d1"), ("7d", "#62acd5")):
            rows = self.data["quotas"][window]["series"]
            counts += len(rows)
            for segment in points_for_plot(rows, w, left, right, top, bottom, start, end):
                if len(segment) == 1:
                    x, y = segment[0]
                    canvas.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5,
                                       fill=color, outline="")
                else:
                    flat = [value for point in segment for value in point]
                    canvas.create_line(*flat, fill=color, width=2.5,
                                       joinstyle="round", smooth=False)
        canvas.create_line(left, bottom, right, bottom, fill="#948aab")
        canvas.create_rectangle(right - 182, 4, right - 169, 10, fill="#9677d1", outline="")
        canvas.create_text(right - 165, 7, anchor="w", text="5 小时", fill="#6b6378", font=("Segoe UI", 9))
        canvas.create_rectangle(right - 100, 4, right - 87, 10, fill="#62acd5", outline="")
        canvas.create_text(right - 83, 7, anchor="w", text="每周", fill="#6b6378", font=("Segoe UI", 9))
        if counts == 0:
            canvas.create_text(w / 2, h / 2, text="尚无历史：从本次启动开始累积记录",
                               fill="#777184")
