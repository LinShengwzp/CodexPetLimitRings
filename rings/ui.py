"""Tiny Windows/Tkinter quota badge for Codex's *native* Mini/Pet.

A transparent single window draws two concentric arcs. All UI colors, sizes,
fonts, padding, and placement are hot-reloaded from config.json. The App Server
query runs off the Tk thread and never uses user tokens.
"""
from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox

from .lifecycle import autostart_command, hidden_creation_flags, restart_command
from .bridge import read_quotas
from .calibration import (
    create_anchor, move_anchor, read_settings, sprite_from_anchor, write_settings,
)
from .config import ConfigWatcher
from .glass import plan_glass
from .core import PetMotionTracker, Quota, Quotas, Rect, follow_position
from .pet import Pet, PetLocator
from .transition import OpacityTransition


COLOR_KEY = "#010203"


class RingWidget:
    def __init__(self, *, demo: bool = False, position_tracer=None):
        self.demo = demo
        self.position_tracer = position_tracer
        self.raw_pet: Pet | None = None
        self._ring_target: tuple[int, int] | None = None
        self._trace_reason = "initializing"
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Codex Pet Limit Rings")
        self.root.overrideredirect(True)
        self.root.configure(bg=COLOR_KEY)
        self.root.wm_attributes("-transparentcolor", COLOR_KEY)
        self.root.wm_attributes("-topmost", True)
        self.fade = OpacityTransition()
        self._opacity_supported = True
        try:
            self.root.wm_attributes("-alpha", 0.0)
        except tk.TclError:
            self._opacity_supported = False
        self._geometry_cache: str | None = None
        try:
            self.root.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.config_watcher = ConfigWatcher()
        self.config_watcher.refresh()
        self.config = self.config_watcher.value
        self.last_config_check = 0.0

        stored = read_settings()
        # V4 is sprite-anchored and independent from V1-V3 host offsets.
        self.offset_x = int(stored.get("offsetX", 0)) if stored.get("layoutVersion") == 4 else 0
        self.offset_y = int(stored.get("offsetY", 0)) if stored.get("layoutVersion") == 4 else 0
        self.offset_x = max(-2500, min(2500, self.offset_x))
        self.offset_y = max(-2500, min(2500, self.offset_y))
        self.calibrations = stored.get("calibrations", {})
        if not isinstance(self.calibrations, dict):
            self.calibrations = {}

        self.locator = PetLocator()
        self.locator.require_uia = self.config["visibility"]["requireUIA"]
        self.pet: Pet | None = None
        self.motion = PetMotionTracker(
            settle_seconds=self.config["position"]["settleMs"] / 1000.0,
        )
        self.preview_origin = (
            self.root.winfo_pointerx() + 22,
            self.root.winfo_pointery() + 22,
        )
        self.width = 1
        self.height = 1
        self.canvas = tk.Canvas(
            self.root, bg=COLOR_KEY, bd=0, highlightthickness=0,
            cursor="fleur",
        )
        self.canvas.pack()
        self.dpi = 96
        self._set_dimensions()

        self.values = Quotas(Quota(41), Quota(91)) if demo else Quotas(Quota(), Quota())
        self.last_success = time.monotonic() if demo else None
        self.error = ""
        self.events: queue.Queue = queue.Queue()
        self.refreshing = False
        self._autostart_busy = False
        self.drag_origin = None
        # Mouse x/y, monitor key, host.right/bottom at previous drag sample.
        self.pet_drag: tuple[int, int, str, int, int] | None = None
        self.pet_drag_settle_until = 0.0
        self.tooltip: tk.Toplevel | None = None
        self.calibration_pending = False
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
            x, y = self.preview_origin
            self._set_ring_visibility(True, time.monotonic(), x, y)
        else:
            self.refresh()
        self.root.after(33, self._tick)

    def _geometry_at(self, x: int, y: int) -> None:
        geometry = f"{self.width}x{self.height}{x:+d}{y:+d}"
        if geometry != self._geometry_cache:
            self.root.geometry(geometry)
            self._geometry_cache = geometry

    def _set_ring_visibility(
        self, visible: bool, now: float,
        x: int | None = None, y: int | None = None,
    ) -> None:
        """Smooth show/hide without restarting native pet tracking.

        Withdraw only once fully transparent, and position before showing.
        Keeping the Tk instance alive enables immediate reappearance when the
        user toggles Mini in Codex.
        """
        if x is not None and y is not None and visible:
            self._geometry_at(x, y)

        config = self.config["animation"]
        fade_in = config["fadeInMs"] / 1000.0 if config["enabled"] else 0.0
        fade_out = config["fadeOutMs"] / 1000.0 if config["enabled"] else 0.0
        if not self._opacity_supported:
            fade_in = fade_out = 0.0
        self.fade.request(visible, now, fade_in=fade_in, fade_out=fade_out)
        alpha = self.fade.advance(now)
        if visible and self.root.state() == "withdrawn":
            # alpha=0 before first mapping prevents a one-frame bright flash.
            if self._opacity_supported:
                try:
                    self.root.wm_attributes("-alpha", alpha)
                except tk.TclError:
                    self._opacity_supported = False
            self.root.deiconify()
            self.root.wm_attributes("-topmost", True)
        if not visible and alpha <= 0.001:
            if self.root.state() != "withdrawn":
                self._hide_tip()
                self.root.withdraw()
            return
        if self._opacity_supported and self.root.state() != "withdrawn":
            try:
                self.root.wm_attributes("-alpha", round(alpha, 3))
            except tk.TclError:
                self._opacity_supported = False

    def _set_dimensions(self) -> None:
        style = self.config
        scale = max(0.8, min(2.3, self.dpi / 96.0))
        outer = style["rings"]["outer"]["diameter"]
        pad = style["background"]["padding"]
        if style["glass"]["enabled"]:
            # Three thin pastel contours instead of the broad shadow whose
            # PNG alpha channel became black in Windows Tk color-key mode.
            pad = max(pad, 8 + style["glass"]["outerMargin"])
        self.width = self.height = round((outer + 2 * pad) * scale)
        self.canvas.config(width=self.width, height=self.height)

    @staticmethod
    def _hex_color(value: str) -> str:
        return value

    def _ring_color(self, quota: Quota, color: str) -> str:
        palette = self.config["rings"]
        if quota.remaining is None:
            return palette["unknownColor"]
        if self.last_success is None or time.monotonic() - self.last_success > 180:
            return palette["unknownColor"]
        if quota.remaining < palette["criticalBelow"]:
            return palette["criticalColor"]
        if quota.remaining < palette["warningBelow"]:
            return palette["warningColor"]
        return color

    def _render(self) -> None:
        self.canvas.delete("all")
        conf = self.config
        scale = max(0.8, min(2.3, self.dpi / 96.0))
        outer = conf["rings"]["outer"]
        inner = conf["rings"]["inner"]
        cx = cy = self.width / 2.0
        bg = conf["background"]
        glass = conf["glass"]
        if glass["enabled"]:
            # Tk transparent-color windows can render transparent PNG pixels
            # as BLACK on some Windows builds. Use safe opaque canvas shapes:
            # a small pastel center, three nearly invisible soft contours,
            # and a little highlight. Everything else is fully transparent.
            plan = plan_glass(
                outer["diameter"], inner["diameter"], inner["stroke"],
                glass, scale,
            )
            shadow_x, shadow_y = plan.shadow_offset
            for radius, color in zip(plan.shadow_radii, plan.shadow_colors):
                self.canvas.create_oval(
                    cx + shadow_x - radius, cy + shadow_y - radius,
                    cx + shadow_x + radius, cy + shadow_y + radius,
                    outline=color, width=max(1, round(scale)),
                )
            r = plan.disc_radius
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=plan.disc_fill, outline=plan.disc_rim,
                width=max(1, round(scale)),
            )
            if plan.highlight_opacity:
                self.canvas.create_arc(
                    cx - r + scale, cy - r + scale,
                    cx + r - scale, cy + r - scale,
                    start=35, extent=108, style="arc",
                    outline=plan.highlight, width=max(1, round(scale)),
                )
        elif bg["enabled"]:
            margin = max(1, round(bg["borderWidth"] * scale / 2 + 1))
            self.canvas.create_oval(
                margin, margin, self.width - margin, self.height - margin,
                fill=bg["color"],
                outline=bg["borderColor"] if bg["borderWidth"] > 0 else "",
                width=round(bg["borderWidth"] * scale),
            )

        def ring(quota: Quota, style: dict):
            d = style["diameter"] * scale
            stroke = max(1, round(style["stroke"] * scale))
            box = (cx - d / 2, cy - d / 2, cx + d / 2, cy + d / 2)
            self.canvas.create_oval(
                *box, outline=conf["rings"]["trackColor"], width=stroke,
            )
            if quota.remaining is not None and quota.remaining > 0:
                color = self._ring_color(quota, style["color"])
                if quota.remaining == 100:
                    self.canvas.create_oval(*box, outline=color, width=stroke)
                else:
                    self.canvas.create_arc(
                        *box, start=90, extent=-(quota.remaining * 3.6),
                        style="arc", outline=color, width=stroke,
                    )

        ring(self.values.five_hour, outer)
        ring(self.values.weekly, inner)

        text = conf["text"]
        a = "--" if self.values.five_hour.remaining is None else str(self.values.five_hour.remaining)
        b = "--" if self.values.weekly.remaining is None else str(self.values.weekly.remaining)
        suffix = "%" if text["showPercentSign"] else ""
        label = f"{a}{suffix}{text['separator']}{b}{suffix}"
        weight = "bold" if text["bold"] else "normal"
        self.canvas.create_text(
            cx, cy, text=label, fill=text["color"],
            font=(text["fontFamily"], -max(7, round(text["fontSize"] * scale)), weight),
        )

    def _trace_position(self, event: str = "sample", *, force: bool = False) -> None:
        """Observe both requested geometry and Tk's displayed geometry.

        Important: actual dragon sprite pixels are *not* observed here.
        raw_mascot is Codex state or host approximation; effective_mascot
        includes our manual calibration and cursor-drag predictions.
        """
        if self.position_tracer is None:
            return
        raw = self.raw_pet
        pet = self.pet
        visible = self.root.state() != "withdrawn"
        target = self._ring_target
        window = (
            (self.root.winfo_rootx(), self.root.winfo_rooty(), self.root.winfo_width(), self.root.winfo_height())
            if visible else None
        )
        mouse_x, mouse_y = self.root.winfo_pointerxy()
        config_pos = self.config["position"]
        key = self._monitor_key(pet) if pet is not None else None
        anchor = self.calibrations.get(key) if key else None
        if not isinstance(anchor, dict):
            anchor = None
        rect = lambda r: [r.left, r.top, r.right, r.bottom] if r is not None else None
        fields = {
            "reason": self._trace_reason,
            "visible": visible,
            "pet_hwnd": raw.handle if raw else None,
            "position_source": pet.source if pet else None,
            "position_precise": pet.precise if pet else None,
            "host_rect": rect(raw.host_rect) if raw else None,
            "raw_mascot_rect": rect(raw.rect) if raw else None,
            "effective_mascot_rect": rect(pet.rect) if pet else None,
            "monitor_work_area": rect(pet.work_area) if pet else None,
            "dpi": pet.dpi if pet else None,
            "ring_target_rect": ([target[0], target[1], target[0] + self.width, target[1] + self.height]
                                 if target is not None else None),
            "ring_window_observed": list(window) if window is not None else None,
            "ring_size": [self.width, self.height],
            "ring_drag_offset": [self.offset_x, self.offset_y],
            "config_offset": [config_pos["offsetX"], config_pos["offsetY"]],
            "config_anchor": [config_pos["side"], config_pos["gap"], config_pos["verticalRatio"]],
            "calibration_active": anchor is not None,
            "calibration_insets": {
                "rightInset": anchor.get("rightInset"),
                "bottomInset": anchor.get("bottomInset"),
            } if anchor else None,
            "mouse_xy": [mouse_x, mouse_y],
            "left_mouse_down": self._mouse_pressed(),
            "pet_drag_tracking": self.pet_drag is not None,
            "ring_dragging": self.drag_origin is not None,
            "calibration_pending": self.calibration_pending,
        }
        self.position_tracer.emit(event, fields, force=force)

    def _monitor_key(self, pet: Pet) -> str:
        area = pet.work_area
        return f"{area.left},{area.top},{area.right},{area.bottom}"

    def _effective_rect(self, pet: Pet) -> Rect:
        if pet.precise:
            return pet.rect
        anchor = self.calibrations.get(self._monitor_key(pet))
        calibrated = sprite_from_anchor(pet.host_rect, anchor)
        return calibrated or pet.rect

    def _effective_pet(self, pet: Pet) -> Pet:
        rect = self._effective_rect(pet)
        if rect is pet.rect:
            return pet
        from dataclasses import replace
        return replace(pet, rect=rect, source="manually-calibrated", precise=True)

    @staticmethod
    def _mouse_pressed() -> bool:
        if os.name != "nt":
            return False
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        except (OSError, AttributeError):
            return False

    def _handle_pet_drag(self, pet: Pet, now: float) -> bool:
        """Track vertical/horizontal sprite drags even if host HWND is static.

        Only activate after calibration when click began near the calibrated
        mascot. Never infer a sprite drag from the whole full-screen host.
        """
        if self.drag_origin is not None or self.calibration_pending:
            return False
        key = self._monitor_key(pet)
        anchor = self.calibrations.get(key)
        if not isinstance(anchor, dict) or pet.source != "manually-calibrated":
            return False

        mx, my = self.root.winfo_pointerxy()
        down = self._mouse_pressed()
        if not down:
            if self.pet_drag:
                self.pet_drag = None
                self.pet_drag_settle_until = now + 0.6
                write_settings({"calibrations": self.calibrations})
            return now < self.pet_drag_settle_until

        host = pet.host_rect
        if self.pet_drag is None:
            rect = pet.rect
            if rect.left - 22 <= mx <= rect.right + 22 and rect.top - 22 <= my <= rect.bottom + 22:
                self.pet_drag = (mx, my, key, host.right, host.bottom)
        else:
            x, y, dragging_key, previous_right, previous_bottom = self.pet_drag
            if dragging_key == key:
                cursor_dx, cursor_dy = mx - x, my - y
                host_dx, host_dy = host.right - previous_right, host.bottom - previous_bottom
                if cursor_dx or cursor_dy or host_dx or host_dy:
                    self.calibrations[key] = move_anchor(
                        anchor, cursor_dx, cursor_dy,
                        host_dx=host_dx, host_dy=host_dy,
                    )
                    self.pet_drag = (mx, my, key, host.right, host.bottom)
        return self.pet_drag is not None

    def _tick(self) -> None:
        now = time.monotonic()
        if now - self.last_config_check >= 1.0:
            self.last_config_check = now
            if self.config_watcher.refresh():
                self.config = self.config_watcher.value
                self.motion.settle_seconds = self.config["position"]["settleMs"] / 1000.0
                self.locator.require_uia = self.config["visibility"]["requireUIA"]
                self._geometry_cache = None
                self._set_dimensions()
                self._render()

        while True:
            try:
                status, value = self.events.get_nowait()
            except queue.Empty:
                break
            if status == "autostart_result":
                self._autostart_busy = False
                action, success, detail = value
                title = {"Install": "启用开机自启", "Remove": "停用开机自启", "Status": "开机自启状态"}[action]
                if success:
                    messagebox.showinfo(title, detail, parent=self.root)
                else:
                    messagebox.showerror(title + "失败", detail, parent=self.root)
                continue
            self.refreshing = False
            self._hide_tip()
            if status == "ok":
                self.values = value
                self.last_success = time.monotonic()
                self.error = ""
            else:
                self.error = str(value)
            self._render()

        if self.drag_origin is None:
            try:
                raw_pet = self.locator.find()
            except Exception as exc:
                raw_pet = None
                self.error = f"Codex Pet 检测失败：{exc}"
            self.raw_pet = raw_pet
            if raw_pet is None:
                self._trace_reason = "pet_not_found"
                self._ring_target = None
                self.motion.reset()
                self.pet = None
                self.pet_drag = None
                if self.demo:
                    x, y = self.preview_origin
                    self._set_ring_visibility(True, now, x + self.offset_x, y + self.offset_y)
                else:
                    self._set_ring_visibility(False, now)
            else:
                if self.pet is None or self.pet.dpi != raw_pet.dpi:
                    self.dpi = raw_pet.dpi
                    self._set_dimensions()
                    self._render()
                effective_pet = self._effective_pet(raw_pet)
                pet_dragging = self._handle_pet_drag(effective_pet, now)
                # _handle_pet_drag may update calibration, so recompute.
                effective_pet = self._effective_pet(raw_pet)
                self.pet = effective_pet
                position = self.config["position"]
                # Apply config offsets *in addition* to user drag offsets.
                x, y = follow_position(
                    effective_pet.rect, self.width, self.height,
                    effective_pet.work_area,
                    self.offset_x + position["offsetX"],
                    self.offset_y + position["offsetY"],
                    side=position["side"],
                    gap=position["gap"],
                    vertical_ratio=position["verticalRatio"],
                )
                self._ring_target = (x, y)
                settled = self.motion.should_show(effective_pet.rect, effective_pet.handle, now)
                moving = pet_dragging or now < self.pet_drag_settle_until
                self._trace_reason = (
                    "pet_drag" if pet_dragging else
                    "drag_release_settling" if moving else
                    "host_or_mascot_settling" if not settled else
                    "visible"
                )
                should_show = self.demo or (settled and not moving)
                self._set_ring_visibility(should_show, now, x, y)
                if not should_show:
                    self._hide_tip()
        if self.drag_origin is not None:
            self._trace_reason = "ring_drag"
        self._trace_position()
        frame_ms = self.config["animation"]["frameMs"]
        if self.fade.alpha in (0.0, 1.0) and self.fade.target == self.fade.alpha:
            frame_ms = max(90, frame_ms)
        self.root.after(frame_ms, self._tick)

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
        start_x, start_y, offset_x, offset_y = self.drag_origin
        self.offset_x = max(-2500, min(2500, offset_x + event.x_root - start_x))
        self.offset_y = max(-2500, min(2500, offset_y + event.y_root - start_y))
        if self.demo and self.pet is None:
            x, y = self.preview_origin
            self.root.geometry(f"{x + self.offset_x:+d}{y + self.offset_y:+d}")
        elif self.pet is not None:
            p = self.config["position"]
            px, py = follow_position(
                self.pet.rect, self.width, self.height, self.pet.work_area,
                self.offset_x + p["offsetX"], self.offset_y + p["offsetY"],
                side=p["side"], gap=p["gap"], vertical_ratio=p["verticalRatio"],
            )
            self._ring_target = (px, py)
            self.root.geometry(f"{self.width}x{self.height}{px:+d}{py:+d}")
        self._trace_reason = "ring_drag"
        self._trace_position("ring_drag")

    def _end_drag(self, _event) -> None:
        if self.drag_origin is not None:
            self.drag_origin = None
            write_settings({"layoutVersion": 4, "offsetX": self.offset_x, "offsetY": self.offset_y})
            self._trace_reason = "ring_drag_released"
            self._trace_position("ring_drag_end", force=True)

    def _detail_lines(self) -> list[str]:
        five = self.values.five_hour
        week = self.values.weekly
        return [
            f"5 小时：{five.remaining if five.remaining is not None else '--'}% · {five.reset_label()}",
            f"每周：{week.remaining if week.remaining is not None else '--'}% · {week.reset_label()}",
            "演示数据" if self.demo else (
                "数据过期或查询失败" if self.last_success is None or time.monotonic() - self.last_success > 180
                else "额度已刷新"
            ),
            *(([self.error[:100]]) if self.error else []),
        ]

    def _show_tip(self, _event=None) -> None:
        if self.drag_origin or self.tooltip:
            return
        tip = tk.Toplevel(self.root)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.configure(bg="#eee8f5")
        tk.Label(
            tip, text="\n".join(self._detail_lines()), justify="left",
            fg="#594d72", bg="#eee8f5", padx=10, pady=7,
            font=("Microsoft YaHei UI", 9),
        ).pack()
        tip.geometry(f"{self.root.winfo_rootx():+d}{self.root.winfo_rooty() - 85:+d}")
        tip.wm_attributes("-topmost", True)
        tip.deiconify()
        self.tooltip = tip

    def _hide_tip(self) -> None:
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

    def _reset_position(self) -> None:
        self.offset_x = self.offset_y = 0
        write_settings({"layoutVersion": 4, "offsetX": 0, "offsetY": 0})

    def _calibrate(self) -> None:
        """Five seconds to move the pointer to the mascot's center."""
        if self.calibration_pending:
            return
        self.calibration_pending = True
        self._trace_reason = "calibration_started"
        self._trace_position("calibration_start", force=True)
        self._hide_tip()
        self.root.after(5000, self._finish_calibration)

    def _finish_calibration(self) -> None:
        self.calibration_pending = False
        try:
            raw_pet = self.locator.find()
            if raw_pet is None:
                self.error = "校准失败：Codex Mini 未显示"
                return
            cx, cy = self.root.winfo_pointerxy()
            area = raw_pet.work_area
            # Avoid saving an anchor on an unrelated monitor.
            if not (area.left <= cx < area.right and area.top <= cy < area.bottom + 80):
                self.error = "校准失败：鼠标不在小龙娘所在屏幕"
                return
            key = self._monitor_key(raw_pet)
            self.calibrations[key] = create_anchor(raw_pet.host_rect, cx, cy)
            self.offset_x = self.offset_y = 0
            self.pet_drag = None
            self.motion.reset()
            write_settings({
                "layoutVersion": 4, "offsetX": 0, "offsetY": 0,
                "calibrations": self.calibrations,
            })
            self.error = ""
        except (OSError, ValueError, TypeError) as exc:
            self.error = f"校准失败：{exc}"
        finally:
            self._trace_reason = "calibration_finished"
            self._trace_position("calibration_end", force=True)

    def _clear_calibration(self) -> None:
        if self.pet is not None:
            key = self._monitor_key(self.pet)
            self.calibrations.pop(key, None)
            write_settings({"calibrations": self.calibrations})
            self.motion.reset()
            self._trace_reason = "calibration_cleared"
            self._trace_position("calibration_cleared", force=True)

    def _manage_autostart(self, mode: str) -> None:
        """Run bundled autostart management off the Tk/UIA thread."""
        if self._autostart_busy:
            return
        self._autostart_busy = True

        def worker():
            try:
                result = subprocess.run(
                    autostart_command(mode),
                    cwd=str(autostart_command.__globals__["ROOT"]),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=25,
                    creationflags=hidden_creation_flags(),
                    check=False,
                )
                success = result.returncode == 0
                detail = (result.stdout if success else result.stderr or result.stdout).strip()
                if not detail:
                    detail = "操作完成。" if success else f"PowerShell 返回错误码 {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                success, detail = False, str(exc)
            self.events.put(("autostart_result", (mode, success, detail[:1500])))

        threading.Thread(target=worker, daemon=True, name="codex-pet-autostart").start()

    def _restart_app(self) -> None:
        """Release the single-instance mutex before a fresh instance starts."""
        if self.demo:
            return
        try:
            subprocess.Popen(
                restart_command(os.getpid()),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden_creation_flags(),
                close_fds=True,
            )
        except OSError as exc:
            messagebox.showerror("重新启动失败", str(exc), parent=self.root)
            return
        self.close()

    def _show_menu(self, event) -> None:
        self._hide_tip()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Codex Mini · 5h / 7d", state="disabled")
        menu.add_separator()
        menu.add_command(
            label="立即刷新额度", command=self.refresh,
            state="disabled" if self.demo else "normal",
        )
        menu.add_command(
            label="校准小龙娘位置（5秒内把鼠标移到她的中心）",
            command=self._calibrate,
        )
        menu.add_command(label="清除此屏幕的校准", command=self._clear_calibration)
        menu.add_command(label="恢复圆环默认偏移", command=self._reset_position)
        menu.add_separator()
        menu.add_command(
            label="重新启动圆环",
            command=self._restart_app,
            state="disabled" if self.demo else "normal",
        )
        menu.add_command(
            label="启用开机自启", command=lambda: self._manage_autostart("Install"),
            state="disabled" if self._autostart_busy else "normal",
        )
        menu.add_command(
            label="停用开机自启", command=lambda: self._manage_autostart("Remove"),
            state="disabled" if self._autostart_busy else "normal",
        )
        menu.add_command(
            label="查看自启状态", command=lambda: self._manage_autostart("Status"),
            state="disabled" if self._autostart_busy else "normal",
        )
        menu.add_separator()
        menu.add_command(label="退出圆环（不关闭宠物）", command=self.close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def close(self) -> None:
        self.locator.close()
        self._trace_reason = "exit"
        self._trace_position("exit", force=True)
        self._hide_tip()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
