"""Custom canvas widgets: the mic indicator and the level equalizer."""

from __future__ import annotations

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from . import theme
from .app import State

# Plain tk.Canvas ovals/arcs have zero anti-aliasing (a bare rasterized
# ellipse), which looks heavily pixelated at these sizes — worse under
# Windows DPI scaling. Rendering at a higher resolution with PIL and
# downsampling with a LANCZOS filter (supersampling) gives genuinely smooth
# circles without pulling in a real vector-graphics dependency.
_SUPERSAMPLE = 4


def aa_image(width: int, height: int, bg: str, draw) -> ImageTk.PhotoImage:
    """Render `draw(pil_draw, scale)` onto a supersampled canvas and return a
    downsampled (anti-aliased) PhotoImage ready for Canvas.create_image.
    The caller must keep the returned PhotoImage referenced (e.g. on an
    instance attribute) — Tk drops images with no live Python reference."""
    k = _SUPERSAMPLE
    img = Image.new("RGB", (width * k, height * k), bg)
    draw(ImageDraw.Draw(img), k)
    img = img.resize((width, height), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class MicIndicator(tk.Canvas):
    """A round mic indicator that changes colour by state and pulses while
    recording."""

    def __init__(self, master, size: int = 132, bg: str = theme.CARD) -> None:
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._size = size
        self._bg = bg
        self._state = State.IDLE
        self._pulse = 0.0
        self._pulsing = False
        self._photo = None  # keep alive — Tk drops unreferenced PhotoImages
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
        s = self._size
        c = s / 2
        color = theme.STATE_COLOR.get(self._state, theme.ACCENT)
        # Outer soft halo (pulses while recording).
        base_r = s * 0.42
        halo = base_r + (math.sin(self._pulse) * 6 if self._pulsing else 0)
        ring_color = theme.ACCENT_DIM if self._state is State.IDLE else color
        r = s * 0.30

        def draw(d: ImageDraw.ImageDraw, k: int) -> None:
            cc = c * k

            def circle(radius: float, **kw) -> None:
                rr = radius * k
                d.ellipse([cc - rr, cc - rr, cc + rr, cc + rr], **kw)

            circle(halo, outline=ring_color, width=max(1, round(2 * k)))
            # inner faint stroke ring
            circle(halo - 8, outline=theme.STROKE, width=max(1, round(k)))
            # main disc
            circle(r, fill=color)

        self._photo = aa_image(s, s, self._bg, draw)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)
        # Glyph — must contrast with the disc, not just "white": bright
        # accent colours (e.g. geek-black's neon green) make white nearly
        # invisible, same problem as button text on an accent background.
        self.create_text(c, c, text=theme.STATE_GLYPH.get(self._state, "🎙"),
                         fill=theme.ON_ACCENT, font=("Segoe UI Emoji", int(s * 0.22)))


class Equalizer(tk.Canvas):
    """A row of animated bars driven by the mic level (0..1)."""

    def __init__(self, master, width: int = 300, height: int = 46,
                 bars: int = 27, bg: str = theme.CARD) -> None:
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self._width = width
        self._height = height
        self._n = bars
        self._bg = bg
        self._level = 0.0
        self._phase = 0.0
        self._active = False
        self._photo = None
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
        gap = 3
        bw = (self._width - gap * (self._n - 1)) / self._n
        mid = self._height / 2
        bars = []
        for i in range(self._n):
            # Bell-shaped envelope so centre bars are tallest.
            env = math.sin(math.pi * (i + 0.5) / self._n)
            wobble = 0.55 + 0.45 * math.sin(self._phase + i * 0.5)
            h = 4 + (self._height - 8) * self._level * env * wobble
            x0 = i * (bw + gap)
            x1 = x0 + bw
            color = theme.ACCENT if self._level > 0.02 else theme.STROKE
            r = min(bw / 2, h / 2)
            bars.append((x0, mid - h / 2, x1, mid + h / 2, r, color))

        # One supersampled image for the whole row (not one per bar) — far
        # cheaper than 27 separate PIL renders at the animation's frame rate.
        def draw(d: ImageDraw.ImageDraw, k: int) -> None:
            for x0, y0, x1, y1, r, color in bars:
                d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=max(1, r * k), fill=color)

        self._photo = aa_image(self._width, self._height, self._bg, draw)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)
