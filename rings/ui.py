"""Tiny transparent Tkinter HUD; native Codex pet stays untouched."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

from .bridge import read_quotas
from .core import Quota, Quotas, Rect, follow_position
from .pet import PetLocator


COLOR_KEY = "#010203"
COLOR_5H = "#aa8bda"
COLOR_WEEK = "#80b8e1"
COLOR_TRACK = "#d8d2e4"
COLOR_OLD = "#97949f"
COLOR_WARN = "#e6b15f"
COLOR_CRITICAL = "#ec797d"


def config_file() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodexPetLimitRings"
    return root / "settings.json"


def load_offsets() -> tuple[int, int]:
    try:
        data = json.loads(config_file().read_text(encoding="utf-8"))
        return (
            max(-1500, min(1500, int(data.get("offsetX", 0)))),
            max(-1500, min(1500, int(data.get("offsetY", 0)))),
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return 0, 0


def save_offsets(x: int, y: int) -> None:
    file = config_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + ".tmp")
    temp.write_text(json.dumps({"offsetX": x, "offsetY": y}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(file)


class RingWidget:
    def __init__(self, *, demo: bool = False):
        self.demo = demo
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Codex Pet Limit Rings")
        self.root.overrideredirect(True)
        self.root.configure(bg=COLOR_KEY)
        # Windows color-key transparency keeps the desktop pet underneath visible.
        self.root.wm_attributes("-transparentcolor", COLOR_KEY)
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.offset_x, self.offset_y = load_offsets()
        self.locator = None if demo else PetLocator()
        self.pet = None
        self.diameter = 52
        self.spacing = 9
        self.padding = 7
        self.width = 2 * self.diameter + self.spacing + 2 * self.padding
        self.height = self.diameter + 22
        self.canvas = tk.Canvas(
            self.root, width=self.width, height=self.height, bg=COLOR_KEY,
            bd=0, highlightthickness=0, cursor="fleur",
        )
        self.canvas.pack()
        self.values = Quotas(Quota(53), Quota(93)) if demo else Quotas(Quota(), Quota())
        self.last_success = time.monotonic() if demo else None
        self.error = ""
        self.events: queue.Queue = queue.Queue()
        self.refreshing = False
        self.drag_origin = None
        self.tooltip: tk.Toplevel | None = None
        self._render()

        self.canvas.bind("<ButtonPress-1>", self._begin_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Enter>", self._show_tip)
        self.canvas.bind("<Leave>", lambda event: self._hide_tip())
        self.canvas.bind("<Double-Button-1>", lambda event: self.refresh())
        self.root.bind("<Escape>", lambda event: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        if demo:
            self.root.geometry(f"{self.width}x{self.height}+100+100")
            self.root.deiconify()
        else:
            self.refresh()
        self.root.after(400, self._tick)

    def _sizes(self, dpi: int) -> None:
        # Tk is made DPI-aware by main.py. Canvas pixel dimensions are physical.
        scale = max(0.8, min(2.4, dpi / 96))
        diameter = round(52 * scale)
        spacing = round(9 * scale)
        padding = round(7 * scale)
        width = 2 * diameter + spacing + 2 * padding
        height = diameter + round(22 * scale)
        if (width, height) != (self.width, self.height):
            self.diameter, self.spacing, self.padding = diameter, spacing, padding
            self.width, self.height = width, height
            self.canvas.config(width=width, height=height)
            self._render()

    def _ring_color(self, quota: Quota, normal: str) -> str:
        if quota.remaining is None:
            return COLOR_OLD
        if self.last_success is None or time.monotonic() - self.last_success > 180:
            return COLOR_OLD
        if quota.remaining < 10:
            return COLOR_CRITICAL
        if quota.remaining < 20:
            return COLOR_WARN
        return normal

    def _render(self) -> None:
        self.canvas.delete("all")
        d = self.diameter
        scale = d / 52
        for i, (q, label, normal) in enumerate((
            (self.values.five_hour, "5h", COLOR_5H),
            (self.values.weekly, "7d", COLOR_WEEK),
        )):
            x = self.padding + i * (d + self.spacing)
            inset = round(4 * scale)
            self.canvas.create_arc(
                x + inset, inset, x + d - inset, d - inset,
                start=0, extent=359.9, style="arc", outline=COLOR_TRACK,
                width=max(2, round(5 * scale)),
            )
            color = self._ring_color(q, normal)
            if q.remaining is not None and q.remaining > 0:
                self.canvas.create_arc(
                    x + inset, inset, x + d - inset, d - inset,
                    start=90, extent=-min(359.9, q.remaining * 3.599),
                    style="arc", outline=color, width=max(2, round(5 * scale)),
                )
            center = x + d / 2
            percentage = "--" if q.remaining is None else f"{q.remaining}%"
            self.canvas.create_text(
                center, d / 2, text=percentage, fill=color,
                font=("Segoe UI", -max(10, round(12 * scale)), "bold"),
            )
            self.canvas.create_text(
                center, d + round(9 * scale), text=label, fill="#9384a6",
                font=("Segoe UI", -max(9, round(10 * scale))),
            )

    def _tick(self) -> None:
        while True:
            try:
                status, value = self.events.get_nowait()
            except queue.Empty:
                break
            self.refreshing = False
            if status == "ok":
                self.values = value
                self.last_success = time.monotonic()
                self.error = ""
            else:
                self.error = str(value)
            self._render()

        if not self.demo:
            try:
                pet = self.locator.find()
            except Exception as exc:
                pet = None
                self.error = f"宠物窗口定位失败：{exc}"
            if pet is None:
                if self.root.state() != "withdrawn":
                    self.root.withdraw()
                self.pet = None
            else:
                if self.pet is None or self.pet.dpi != pet.dpi:
                    self._sizes(pet.dpi)
                self.pet = pet
                x, y = follow_position(
                    pet.rect, self.width, self.height, pet.work_area,
                    self.offset_x, self.offset_y,
                )
                self.root.geometry(f"{self.width}x{self.height}{x:+d}{y:+d}")
                if self.root.state() == "withdrawn":
                    self.root.deiconify()
                    self.root.wm_attributes("-topmost", True)
        self.root.after(400, self._tick)

    def refresh(self) -> None:
        if self.demo or self.refreshing:
            return
        self.refreshing = True

        def work():
            try:
                self.events.put(("ok", read_quotas()))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True, name="codex-quota-query").start()
        self.root.after(60000, self.refresh)

    def _begin_drag(self, event) -> None:
        self._hide_tip()
        self.drag_origin = (event.x_root, event.y_root, self.offset_x, self.offset_y)

    def _drag(self, event) -> None:
        if self.drag_origin is None:
            return
        x, y, ox, oy = self.drag_origin
        self.offset_x = max(-1500, min(1500, ox + event.x_root - x))
        self.offset_y = max(-1500, min(1500, oy + event.y_root - y))
        if self.demo:
            self.root.geometry(f"+{max(0, 100 + self.offset_x)}+{max(0, 100 + self.offset_y)}")
        elif self.pet is not None:
            px, py = follow_position(
                self.pet.rect, self.width, self.height, self.pet.work_area,
                self.offset_x, self.offset_y,
            )
            self.root.geometry(f"{self.width}x{self.height}{px:+d}{py:+d}")

    def _end_drag(self, event) -> None:
        if self.drag_origin is not None:
            self.drag_origin = None
            save_offsets(self.offset_x, self.offset_y)

    def _detail_lines(self) -> list[str]:
        return [
            f"5 小时：{self.values.five_hour.remaining if self.values.five_hour.remaining is not None else '--'}% · {self.values.five_hour.reset_label()}",
            f"每周：{self.values.weekly.remaining if self.values.weekly.remaining is not None else '--'}% · {self.values.weekly.reset_label()}",
            "演示数据" if self.demo else (
                "数据已过期 / 重新刷新" if self.last_success is None or time.monotonic() - self.last_success > 180
                else "最近成功刷新：额度可用"
            ),
            *(([self.error[:100]]) if self.error else []),
        ]

    def _show_tip(self, event) -> None:
        if self.drag_origin is not None or self.tooltip is not None:
            return
        tip = tk.Toplevel(self.root)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.configure(bg="#eee8f5")
        text = "\n".join(self._detail_lines())
        tk.Label(
            tip, text=text, justify="left", fg="#594d72", bg="#eee8f5",
            padx=10, pady=7, font=("Microsoft YaHei UI", 9),
        ).pack()
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty() - 85
        tip.geometry(f"+{max(0, x)}+{max(0, y)}")
        tip.wm_attributes("-topmost", True)
        tip.deiconify()
        self.tooltip = tip

    def _hide_tip(self) -> None:
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

    def _reset_position(self) -> None:
        self.offset_x = self.offset_y = 0
        save_offsets(0, 0)

    def _show_menu(self, event) -> None:
        self._hide_tip()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Codex 原生宠物 · 5h / 7d", state="disabled")
        menu.add_separator()
        menu.add_command(label="立即刷新额度", command=self.refresh, state="disabled" if self.demo else "normal")
        menu.add_command(label="恢复默认位置", command=self._reset_position)
        menu.add_command(label="退出圆环（不关闭宠物）", command=self.close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def close(self) -> None:
        self._hide_tip()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
