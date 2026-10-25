"""Tiny deterministic opacity transition for the transparent HUD.

No tkinter dependence, so fade timing can be unit tested cross-platform.
"""
from __future__ import annotations

from dataclasses import dataclass


def smoothstep(progress: float) -> float:
    t = max(0.0, min(1.0, progress))
    return t * t * (3 - 2 * t)


@dataclass
class OpacityTransition:
    alpha: float = 0.0
    target: float = 0.0
    starting_alpha: float = 0.0
    started_at: float = 0.0
    duration: float = 0.0

    def request(self, visible: bool, now: float, *, fade_in: float, fade_out: float) -> None:
        desired = 1.0 if visible else 0.0
        if desired == self.target:
            return
        self.advance(now)
        self.starting_alpha = self.alpha
        self.target = desired
        self.started_at = now
        self.duration = max(0.0, fade_in if visible else fade_out)
        if self.duration == 0.0:
            self.alpha = desired

    def advance(self, now: float) -> float:
        if self.duration == 0.0:
            self.alpha = self.target
        else:
            t = (now - self.started_at) / self.duration
            self.alpha = (
                self.starting_alpha +
                (self.target - self.starting_alpha) * smoothstep(t)
            )
            if t >= 1.0:
                self.duration = 0.0
                self.alpha = self.target
        return max(0.0, min(1.0, self.alpha))
