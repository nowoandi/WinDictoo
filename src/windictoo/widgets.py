"""Custom canvas widgets: the mic indicator and the level equalizer."""

from __future__ import annotations

import math
import tkinter as tk

from . import theme
from .app import State


class MicIndicator(tk.Canvas):
    """A round mic indicator that changes colour by state and pulses while
    recording."""

    def __init__(self, master, size: int = 132, bg: str = theme.CARD) -> None:
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._size = size
        self._state = State.IDLE
        self._pulse = 0.0
        self._pulsing = False
        self.render()

    def set_state(self, state: State) -> None:
        self._state = state
        if state is State.RECORDING and not self._pulsing:
            self._pulsing = True
            self._animate()
        elif state is not State.RECORDING:
            self._pulsing = False
        self.render()

    def _animate(self) -> None:
        if not self._pulsing:
            return
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self.render()
        self.after(40, self._animate)

    def render(self) -> None:
        self.delete("all")
        s = self._size
        c = s / 2
        color = theme.STATE_COLOR.get(self._state, theme.ACCENT)
        # Outer soft halo (pulses while recording).
        base_r = s * 0.42
        halo = base_r + (math.sin(self._pulse) * 6 if self._pulsing else 0)
        self._ring(c, halo, theme.ACCENT_DIM if self._state is State.IDLE else color, width=2, stipple_fill=True)
        # Main disc.
        r = s * 0.30
        self.create_oval(c - r, c - r, c + r, c + r, fill=color, outline="")
        # Glyph.
        self.create_text(c, c, text=theme.STATE_GLYPH.get(self._state, "🎙"),
                         fill="#ffffff", font=("Segoe UI Emoji", int(s * 0.22)))

    def _ring(self, c: float, r: float, color: str, width: int, stipple_fill: bool) -> None:
        self.create_oval(c - r, c - r, c + r, c + r, outline=color, width=width)
        # inner faint fill ring
        r2 = r - 8
        self.create_oval(c - r2, c - r2, c + r2, c + r2, outline=theme.STROKE, width=1)


class Equalizer(tk.Canvas):
    """A row of animated bars driven by the mic level (0..1)."""

    def __init__(self, master, width: int = 300, height: int = 46,
                 bars: int = 27, bg: str = theme.CARD) -> None:
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self._width = width
        self._height = height
        self._n = bars
        self._level = 0.0
        self._phase = 0.0
        self._active = False
        self.render()

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._level = 0.0
            self.render()

    def set_level(self, level: float) -> None:
        self._level = max(self._level * 0.6, level)  # smooth decay
        self._phase += 0.35
        self.render()

    def render(self) -> None:
        self.delete("all")
        gap = 3
        bw = (self._width - gap * (self._n - 1)) / self._n
        mid = self._height / 2
        for i in range(self._n):
            # Bell-shaped envelope so centre bars are tallest.
            env = math.sin(math.pi * (i + 0.5) / self._n)
            wobble = 0.55 + 0.45 * math.sin(self._phase + i * 0.5)
            h = 4 + (self._height - 8) * self._level * env * wobble
            x0 = i * (bw + gap)
            x1 = x0 + bw
            color = theme.ACCENT if self._level > 0.02 else theme.STROKE
            self._rounded_bar(x0, mid - h / 2, x1, mid + h / 2, bw / 2, color)

    def _rounded_bar(self, x0, y0, x1, y1, r, color) -> None:
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        self.create_oval(x0, y0, x0 + 2 * r, y0 + 2 * r, fill=color, outline="")
        self.create_oval(x1 - 2 * r, y1 - 2 * r, x1, y1, fill=color, outline="")
        self.create_oval(x0, y1 - 2 * r, x0 + 2 * r, y1, fill=color, outline="")
        self.create_oval(x1 - 2 * r, y0, x1, y0 + 2 * r, fill=color, outline="")
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline="")
        self.create_rectangle(x0, y0 + r, x1, y1 - r, fill=color, outline="")
