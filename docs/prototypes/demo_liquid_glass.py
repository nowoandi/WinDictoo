"""Standalone visual prototype: "Liquid Glass" theme + the 7 classical-UI
design rules, evaluated purely for looks. This file is 100% isolated —

- it imports nothing from gui.py / app.py / theme.py / widgets.py,
- it never touches audio, the hotkey, Whisper, or the tray,
- every "state" (recording, hover, pressed...) is faked locally with a
  Tk timer/button, so nothing here can interfere with a real WinDictoo
  session running at the same time.

Run it with:

    uv run python -m windictoo.demo_liquid_glass

Tkinter has no real backdrop blur / light refraction, so "glass" here is
faked the same way most non-native glassmorphism UIs fake it: a translucent
tint alpha-blended over the *known* flat background colour, plus a soft
top-left specular highlight and a darker bottom-right edge (see RULE 1
below). It reads as glass; it isn't literally simulating optics.
"""

from __future__ import annotations

import math
import tkinter as tk

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

_SS = 4  # supersampling factor for anti-aliased edges (same trick as the real app)

# ---------------------------------------------------------------------------
# RULE 6 — Optical alignment grid: every spacing value is a multiple of 4.
SPACING = {"xs": 4, "sm": 8, "md": 16, "lg": 24}

# RULE 2 — Rinner = Router - Padding: an outer 24px radius with 16px padding
# to an inner element gives that inner element an 8px radius (24 - 16 = 8),
# so its curve continues the outer container's arc instead of fighting it.
OUTER_RADIUS = SPACING["lg"]           # 24
PADDING = SPACING["md"]                # 16
INNER_RADIUS = OUTER_RADIUS - PADDING  # 8

WIN_W = 460
CONTENT_W = WIN_W - SPACING["md"] * 2

GLASS_THEMES = {
    "obsidian-violet": {
        "label": "Obsidian Violet Glass", "bg": "#15111f", "base": "#4b2e83",
        "accent": "#a682ff", "text": "#f1ecff", "muted": "#b9a8e0",
    },
    "emerald-mint": {
        "label": "Emerald Mint Glass", "bg": "#0d1c16", "base": "#1f6b4f",
        "accent": "#57e8b0", "text": "#eafff3", "muted": "#9fd9bd",
    },
    "sapphire-ice": {
        "label": "Sapphire Ice Glass", "bg": "#0c1826", "base": "#1c4f78",
        "accent": "#6fd2ff", "text": "#eaf7ff", "muted": "#a4cfe6",
    },
    "rose-quartz": {
        "label": "Rose Quartz Glass", "bg": "#231015", "base": "#7a3a4c",
        "accent": "#ff9fc0", "text": "#fff0f4", "muted": "#e3aebb",
    },
    "amber-gold": {
        "label": "Amber Gold Glass", "bg": "#201708", "base": "#7a5218",
        "accent": "#ffcf6b", "text": "#fff6e6", "muted": "#e0c48c",
    },
    "onyx-neon": {
        "label": "Onyx Neon Glass", "bg": "#020402", "base": "#0e2210",
        "accent": "#39ff14", "text": "#d7ffe0", "muted": "#7fc98d",
    },

    # --- three that change the material, not the hue ----------------------
    # The six above answer "what colour is the glass?". These answer "what if
    # it isn't glass?", which is the question the set was missing: every one
    # of the six is a dark panel, lit from the top left, with the same bevel
    # and the same 24px radius.
    "frosted-daylight": {
        "label": "Frosted Daylight", "bg": "#e7ecf3", "base": "#ffffff",
        "accent": "#2f6df6", "text": "#141922", "muted": "#5b6675",
        # Everything that models depth by darkening fails here. The inner shade
        # becomes a grey smudge on a light panel, and a coloured glow behind the
        # focal point becomes a dirty halo rather than light. Both are off; the
        # shape comes from a bright rim and a dark hairline, which is how frosted
        # glass actually reads against a pale wall.
        "tint": 1.4, "specular": 35, "shade": 0, "rim_light": 255,
        "rim_dark": 60, "glow": 0.0,
    },
    "paper-ink": {
        "label": "Paper & Ink", "bg": "#efe9dd", "base": "#fffdf6",
        "accent": "#c04326", "text": "#191713", "muted": "#6d6658",
        # Deliberately not glass: opaque stock, barely rounded, one printed
        # edge and no glow at all. No specular and no inner shade either —
        # paper is lit evenly, and a bevel is the one thing that would give the
        # imitation away. Here to show whether the layout still holds once the
        # material stops doing the work for it.
        "radius": 8, "tint": 1.7, "specular": 0, "shade": 0,
        "rim_light": 0, "rim_dark": 70, "glow": 0.0,
    },
    "terminal-phosphor": {
        "label": "Terminal Phosphor", "bg": "#050806", "base": "#0b160e",
        "accent": "#4dff88", "text": "#c8ffd7", "muted": "#5c9a70",
        # A CRT has no bevel and nothing round about it: flat panels, hard
        # corners, and every bit of light coming from the phosphor rather than
        # from a lamp somewhere off to the top left. Both rim alphas at zero
        # take the bevel out of glass_panel entirely.
        "radius": 3, "tint": 1.5, "specular": 0, "shade": 0, "rim_light": 0,
        "rim_dark": 0, "glow": 1.8,
    },
}
THEME_ORDER = list(GLASS_THEMES)

# The six palettes above are one material in six hues. These knobs let a
# palette change the *material* instead: how opaque the glass is, whether it
# has a bevel at all, how round it is, how much the focal point glows. Every
# palette that omits a knob keeps exactly the look it had before.
MATERIAL_DEFAULTS = {
    "radius": OUTER_RADIUS,  # outer corner radius; inner is derived from it
    "tint": 1.0,             # multiplier on every panel's opacity
    "specular": 90,          # top-left highlight alpha — 0 makes it matte
    "shade": 55,             # bottom-right shade alpha
    "rim_light": 120,        # lit edge of the two-tone rim
    "rim_dark": 70,          # shaded edge; both 0 removes the bevel entirely
    "glow": 1.0,             # focal-point glow strength — 0 removes it
}


def mat(theme: dict, key: str):
    """One material knob of a palette, or the shared default."""
    return theme.get(key, MATERIAL_DEFAULTS[key])


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def _hex_rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _mix(fg_hex: str, bg_hex: str, alpha: float) -> tuple[int, int, int]:
    fg, bg = _hex_rgb(fg_hex), _hex_rgb(bg_hex)
    return tuple(round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def _mix_hex(fg_hex: str, bg_hex: str, alpha: float) -> str:
    r, g, b = _mix(fg_hex, bg_hex, alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def _resize_rgba(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Downsize an RGBA image without the classic dark-fringe artifact.

    A naive img.resize(..., LANCZOS) treats R/G/B and A independently, so a
    fully-transparent pixel (which is RGB=(0,0,0) with alpha=0) still pulls
    its black colour into neighbouring semi-transparent edge pixels during
    the resampling — exactly the "black corner insertions" visible on the
    rounded buttons before this fix. Premultiplying by alpha before the
    resize (and un-premultiplying after) makes transparent pixels contribute
    zero, not black.
    """
    arr = np.asarray(img).astype(np.float32)
    rgb, a = arr[..., :3], arr[..., 3:4]
    premult = (rgb * (a / 255.0)).astype(np.uint8)
    premult_img = Image.fromarray(premult, "RGB").resize(size, Image.LANCZOS)
    a_img = Image.fromarray(a[..., 0].astype(np.uint8), "L").resize(size, Image.LANCZOS)

    p = np.asarray(premult_img).astype(np.float32)
    a2 = np.asarray(a_img).astype(np.float32)
    safe_a = np.where(a2 < 1, 1, a2)
    rgb_final = np.clip(p / (safe_a[..., None] / 255.0), 0, 255).astype(np.uint8)
    out = np.dstack([rgb_final, a2.astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def _clipped_glow(size: tuple[int, int], mask: Image.Image, cx, cy, r, color, alpha, blur) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def glass_panel(width: int, height: int, radius: int, bg_hex: str, tint_hex: str,
                 *, opacity: float = 0.6, specular: int = 90, shade: int = 55,
                 rim_light_alpha: int = 120, rim_dark_alpha: int = 70) -> Image.Image:
    """RULE 1 (top-left light source): a translucent rounded panel with a
    soft highlight in the upper-left and a darker edge in the lower-right —
    the classical "polished glass/plastic" cue, not a flat colour swatch.

    `bg_hex` must be the colour of whatever this panel sits directly on
    (the window, or a parent panel's own *rendered* fill) — mixing toward
    the wrong background is what caused the mic indicator to visibly not
    match the card behind it."""
    k = _SS
    W, H, R = width * k, height * k, radius * k
    fill = _mix(tint_hex, bg_hex, opacity)

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=255)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=fill + (255,))

    if specular:
        hl = _clipped_glow((W, H), mask, W * 0.15, H * 0.1, min(W, H) * 0.55,
                           (255, 255, 255), specular, R * 0.5)
        img = Image.alpha_composite(img, hl)
    if shade:
        sh = _clipped_glow((W, H), mask, W * 0.88, H * 0.95, min(W, H) * 0.6,
                           (0, 0, 0), shade, R * 0.5)
        img = Image.alpha_composite(img, sh)
    if not (rim_light_alpha or rim_dark_alpha):
        # A flat material has no bevel to draw; the rim below would only put a
        # glassy edge back on something that is meant to read as printed or
        # emitted rather than lit from outside.
        return _resize_rgba(img, (width, height))

    # Two-tone rim along the ACTUAL rounded-rect outline. (A previous version
    # used ImageDraw.arc() here, which draws an ellipse inscribed in the full
    # W x H bounding box — for a wide/short card that's a hugely stretched
    # oval, not a border. rounded_rectangle(outline=...) traces the real
    # shape; a small diagonal gradient mask fades it light-to-dark.)
    lw = max(1, round(2 * k))
    rim_light = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(rim_light).rounded_rectangle([lw, lw, W - lw, H - lw], radius=max(0, R - lw),
                                                 outline=(255, 255, 255, rim_light_alpha), width=lw)
    rim_dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(rim_dark).rounded_rectangle([lw, lw, W - lw, H - lw], radius=max(0, R - lw),
                                                outline=(0, 0, 0, rim_dark_alpha), width=lw)

    # Balanced diagonal split (previous corners were 255/140/140/0, which
    # gave the dark side ~3x more visual weight than the light side).
    grad_seed = Image.new("L", (2, 2))
    grad_seed.putpixel((0, 0), 235)
    grad_seed.putpixel((1, 0), 150)
    grad_seed.putpixel((0, 1), 150)
    grad_seed.putpixel((1, 1), 70)
    grad = grad_seed.resize((W, H), Image.BILINEAR)
    inv_grad = ImageChops.invert(grad)

    rim_light.putalpha(ImageChops.multiply(rim_light.getchannel("A"), grad))
    rim_dark.putalpha(ImageChops.multiply(rim_dark.getchannel("A"), inv_grad))
    img = Image.alpha_composite(img, rim_light)
    img = Image.alpha_composite(img, rim_dark)

    return _resize_rgba(img, (width, height))


def with_outer_glow(img: Image.Image, color_hex: str, pad: int = 26, blur: int = 22,
                    strength: float = 1.0) -> Image.Image:
    """A soft coloured glow behind an element — used only on the hero focal
    point (RULE 3) so it visually wins the room instead of every card
    competing for attention at the same visual weight."""
    w, h = img.size
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    if strength <= 0:
        # Padding is kept even with no glow so the caller's layout maths, which
        # assumes the returned image is bigger than what went in, still holds.
        canvas.paste(img, (pad, pad), img)
        return canvas
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        [pad, pad, pad + w, pad + h], radius=min(w, h) // 2,
        fill=_hex_rgb(color_hex) + (min(255, round(150 * strength)),))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=blur))
    canvas = Image.alpha_composite(canvas, glow)
    canvas.paste(img, (pad, pad), img)
    return canvas


def liquid_lens(size: int, tint_hex: str, pulse: float, active: bool,
                *, specular: int = 140, shade: int = 100) -> Image.Image:
    """The "Liquid Lens" mic indicator: a glass disc with an inner rim shade
    (glass-edge darkening) and a specular highlight blob, inside pulsing
    halo rings while "recording".

    Everything here is drawn with real alpha (never pre-mixed against a
    guessed background colour) so it composites correctly no matter what
    it's pasted on top of — a card, the window, or another lens."""
    k = _SS
    S = size * k
    c = S / 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tint = _hex_rgb(tint_hex)

    base_r = S * 0.42
    halo = base_r + (math.sin(pulse) * S * 0.03 if active else 0)
    ring_alpha = 255 if active else 110
    d.ellipse([c - halo, c - halo, c + halo, c + halo], outline=tint + (ring_alpha,), width=max(1, round(2 * k)))
    halo2 = halo - 10 * k
    d.ellipse([c - halo2, c - halo2, c + halo2, c + halo2],
              outline=tint + (70,), width=max(1, round(k)))

    r = S * 0.32
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([c - r, c - r, c + r, c + r], fill=255)

    disc = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse([c - r, c - r, c + r, c + r], fill=tint_hex)

    if shade:
        rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(rim).ellipse([c - r, c - r, c + r, c + r],
                                    outline=(0, 0, 0, shade), width=round(r * 0.35))
        rim = rim.filter(ImageFilter.GaussianBlur(r * 0.22))
        rim.putalpha(ImageChops.multiply(rim.getchannel("A"), mask))
        disc = Image.alpha_composite(disc, rim)

    if specular:
        hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        hlr = r * 0.5
        hx, hy = c - r * 0.32, c - r * 0.4
        ImageDraw.Draw(hl).ellipse([hx - hlr, hy - hlr, hx + hlr, hy + hlr],
                                   fill=(255, 255, 255, specular))
        hl = hl.filter(ImageFilter.GaussianBlur(r * 0.3))
        hl.putalpha(ImageChops.multiply(hl.getchannel("A"), mask))
        disc = Image.alpha_composite(disc, hl)

    img = Image.alpha_composite(img, disc)
    return _resize_rgba(img, (size, size))


# RULE 5 — four feedback states, expressed as glass opacity: a calm default, a
# brighter hover, a dimmer/"sunken" pressed, and a faint, washed-out disabled.
PILL_OPACITY = {"default": 0.72, "hover": 0.88, "pressed": 0.5, "disabled": 0.18}


def equalizer_image(width: int, height: int, color_hex: str, level: float, phase: float,
                     bars: int = 20) -> Image.Image:
    """Real alpha again (see liquid_lens docstring) — the idle "off" bars
    are just the same colour at low alpha, not pre-mixed toward a guessed
    background."""
    k = _SS
    W, H = width * k, height * k
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tint = _hex_rgb(color_hex)
    gap = 3 * k
    bw = (W - gap * (bars - 1)) / bars
    mid = H / 2
    for i in range(bars):
        env = math.sin(math.pi * (i + 0.5) / bars)
        wobble = 0.5 + 0.5 * math.sin(phase + i * 0.5)
        h = max(3 * k, (H - 6 * k) * level * env * wobble)
        x0 = i * (bw + gap)
        fill = tint + (255,) if level > 0.02 else tint + (80,)
        d.rounded_rectangle([x0, mid - h / 2, x0 + bw, mid + h / 2], radius=bw / 2, fill=fill)
    return _resize_rgba(img, (width, height))


def round_window_region(win: tk.Misc, w: int, h: int, r: int) -> None:
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()
        rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
        ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
    except Exception:  # noqa: BLE001
        pass


class LiquidGlassDemo:
    def __init__(self) -> None:
        self.theme_key = "sapphire-ice"
        self.playing = False
        self._pulse = 0.0
        self._phase = 0.0
        self._level = 0.0
        self.overlay: tk.Toplevel | None = None
        self.settings_sheet: tk.Toplevel | None = None

        self.root = ctk.CTk()
        self.root.title("WinDictoo — Liquid Glass preview (not part of the real app)")
        self.root.geometry(f"{WIN_W}x720")
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._build()

    # -- theme plumbing -------------------------------------------------

    @property
    def t(self) -> dict:
        return GLASS_THEMES[self.theme_key]

    def _blit(self, canvas: tk.Canvas, img: Image.Image, x=0, y=0) -> None:
        photo = ImageTk.PhotoImage(img)
        # Keep the image alive for as long as this specific canvas exists.
        # A single shared list (the previous approach) meant rebuilding the
        # main window — which happens every animation tick while recording —
        # cleared it and garbage-collected the floating overlay's images
        # too, since they'd been appended to the very same list.
        canvas._photo_refs = getattr(canvas, "_photo_refs", [])
        canvas._photo_refs.append(photo)
        canvas.create_image(x, y, anchor="nw", image=photo)

    def _panel(self, w: int, h: int, radius: int, tint_hex: str, opacity: float) -> Image.Image:
        """glass_panel with the active palette's material applied — the single
        place that knows how this palette wants to be rendered."""
        t = self.t
        return glass_panel(w, h, radius, t["bg"], tint_hex,
                           opacity=min(1.0, opacity * mat(t, "tint")),
                           specular=mat(t, "specular"), shade=mat(t, "shade"),
                           rim_light_alpha=mat(t, "rim_light"),
                           rim_dark_alpha=mat(t, "rim_dark"))

    def _lens(self, size: int, tint_hex: str, pulse: float, active: bool) -> Image.Image:
        """The mic lens, likewise following the palette: a matte palette gets a
        flat disc rather than a glass bead with a highlight on it."""
        t = self.t
        spec = round(140 * (mat(t, "specular") / MATERIAL_DEFAULTS["specular"]))
        shade = round(100 * (mat(t, "shade") / MATERIAL_DEFAULTS["shade"]))
        return liquid_lens(size, tint_hex, pulse, active,
                           specular=min(255, spec), shade=min(255, shade))

    def _switch_theme(self, key: str) -> None:
        if key == self.theme_key:
            return
        self.theme_key = key
        self._close_settings_sheet()
        self._build()

    def _close(self) -> None:
        self.root.destroy()

    # -- build ------------------------------------------------------------

    def _build(self) -> None:
        for w in list(self.root.winfo_children()):
            # winfo_children() also lists Toplevels whose master is root (the
            # floating overlay pill, the settings sheet) — a full-window
            # rebuild must not nuke those.
            if isinstance(w, tk.Toplevel):
                continue
            w.destroy()
        t = self.t
        # Radius comes from the palette now: a printed or emitted material is
        # not round the way glass is. The inner radius still follows RULE 2
        # (Rinner = Router - Padding), floored so a nearly square palette does
        # not ask for a negative one.
        self.radius = mat(t, "radius")
        self.inner_radius = max(2, self.radius - PADDING)
        self.root.configure(fg_color=t["bg"])

        outer = ctk.CTkFrame(self.root, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])

        self._build_header(outer, t)
        self._build_hero(outer, t)
        self._build_chips(outer, t)
        self._build_start(outer, t)
        self._build_result(outer, t)
        self._build_footer(outer, t)

    def _build_header(self, parent, t) -> None:
        # Simplified per feedback: a single glass menu button (⋮), matching
        # the real app — theme selection lives *inside* the settings sheet
        # it opens, not as a second icon floating in the header.
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, SPACING["md"]))
        ctk.CTkLabel(row, text="WinDictoo", font=_font(22, "bold"), text_color=t["text"]).pack(side="left")
        ctk.CTkLabel(row, text="Liquid Glass preview", font=_font(11), text_color=t["muted"]).pack(
            side="left", padx=(SPACING["sm"], 0))

        menu_canvas = tk.Canvas(row, width=40, height=40, bg=t["bg"], highlightthickness=0, cursor="hand2")
        menu_canvas.pack(side="right")
        img = self._panel(40, 40, self.inner_radius, t["base"], 0.5)
        self._blit(menu_canvas, img)
        menu_canvas.create_text(20, 18, text="⋮", fill=t["text"], font=("Segoe UI", 16, "bold"))
        menu_canvas.bind("<Button-1>", lambda _e: self._open_settings_sheet())

    def _build_hero(self, parent, t) -> None:
        # RULE 3 — single focal point: the mic gets the glow and the biggest
        # glass surface; everything else is visually quieter. The Start
        # action used to overlap this same card (feedback: it read as if it
        # were part of the dictation display) — it's now its own element
        # below, matching the real app's separate hero-card / button split.
        hero_h = 220
        canvas = tk.Canvas(parent, width=CONTENT_W, height=hero_h, bg=t["bg"], highlightthickness=0)
        canvas.pack(fill="x", pady=(0, SPACING["sm"]))
        card = self._panel(CONTENT_W, hero_h, self.radius, t["base"], 0.5)
        self._blit(canvas, card)

        mic_size = 110
        mic_img = self._lens(mic_size, t["accent"], self._pulse, self.playing)
        glowed = with_outer_glow(mic_img, t["accent"], pad=20, blur=20,
                                 strength=mat(t, "glow"))
        mx = (CONTENT_W - glowed.width) // 2
        my = 18
        self._blit(canvas, glowed, mx, my)
        canvas.create_text(mx + glowed.width // 2, my + glowed.height // 2, text="🎙",
                            fill=t["text"], font=("Segoe UI Emoji", int(mic_size * 0.22)))

        status = "Слушаю…" if self.playing else "Готов к диктовке"
        status_y = my + glowed.height + 16
        canvas.create_text(CONTENT_W // 2, status_y, text=status, fill=t["text"], font=("Segoe UI", 14, "bold"))

        eq_w, eq_h = 200, 30
        eq_img = equalizer_image(eq_w, eq_h, t["accent"], self._level, self._phase)
        self._blit(canvas, eq_img, (CONTENT_W - eq_w) // 2, status_y + 18)

    def _build_chips(self, parent, t) -> None:
        # RULE 4-adjacent: these are read-only *info* chips (hotkey, mode),
        # not interactive settings — those moved into the settings sheet.
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, SPACING["sm"]))
        chip_w = (CONTENT_W - SPACING["sm"]) // 2
        for text in ("⌨  Ctrl + Space", "⏱  удержание"):
            c = tk.Canvas(row, width=chip_w, height=36, bg=t["bg"], highlightthickness=0)
            c.pack(side="left", padx=(0, SPACING["sm"]))
            img = self._panel(chip_w, 36, self.inner_radius, t["base"], 0.3)
            self._blit(c, img)
            c.create_text(chip_w // 2, 18, text=text, fill=t["muted"], font=("Segoe UI", 11))

    def _build_start(self, parent, t) -> None:
        pill_h = 48
        canvas = tk.Canvas(parent, width=CONTENT_W, height=pill_h, bg=t["bg"], highlightthickness=0,
                          cursor="hand2")
        canvas.pack(fill="x", pady=(0, SPACING["md"]))
        self._start_canvas = canvas
        self._draw_pill("default")
        canvas.bind("<Button-1>", lambda _e: self._toggle_play())
        canvas.bind("<Enter>", lambda _e: self._draw_pill("hover"))
        canvas.bind("<Leave>", lambda _e: self._draw_pill("default"))
        canvas.bind("<ButtonPress-1>", lambda _e: self._draw_pill("pressed"))

    def _draw_pill(self, state: str) -> None:
        t = self.t
        c = self._start_canvas
        c.delete("all")
        # A pill stays a pill only while the palette is round; a square-cornered
        # material would look borrowed with a 24px lozenge in the middle of it.
        img = self._panel(CONTENT_W, 48, min(24, self.radius), t["accent"],
                          PILL_OPACITY[state])
        self._blit(c, img)
        label = "⏹   Стоп" if self.playing else "▶   Старт"
        c.create_text(CONTENT_W // 2, 24, text=label, fill=t["text"], font=("Segoe UI", 14, "bold"))

    def _toggle_play(self) -> None:
        self.playing = not self.playing
        self._draw_pill("default")
        if self.playing:
            self._animate()
        else:
            self._level = 0.0
            self._build_hero_refresh()

    def _build_hero_refresh(self) -> None:
        # cheapest correct way to reflect state without hand-rolling partial
        # redraws for a one-off prototype: rebuild the whole window.
        self._build()

    def _animate(self) -> None:
        if not self.playing:
            return
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self._phase += 0.3
        self._level = min(1.0, self._level * 0.7 + 0.5 + 0.3 * math.sin(self._phase))
        self._build_hero_refresh()
        self.root.after(60, self._animate)

    def _build_result(self, parent, t) -> None:
        # Secondary focal weight (RULE 3): softer opacity than the hero, but
        # not so faint the text becomes hard to read — feedback flagged
        # readability as a hard requirement regardless of theme.
        h = 130
        canvas = tk.Canvas(parent, width=CONTENT_W, height=h, bg=t["bg"], highlightthickness=0)
        canvas.pack(fill="x", pady=(0, SPACING["md"]))
        card = self._panel(CONTENT_W, h, self.inner_radius, t["base"], 0.34)
        self._blit(canvas, card)
        canvas.create_text(PADDING, SPACING["sm"], anchor="nw", text="РАСПОЗНАННЫЙ ТЕКСТ",
                            fill=t["muted"], font=("Segoe UI", 9, "bold"))

        copy_w, copy_h = 96, 26
        copy_img = self._panel(copy_w, copy_h, self.inner_radius, t["base"], 0.6)
        self._blit(canvas, copy_img, CONTENT_W - PADDING - copy_w, SPACING["xs"])
        canvas.create_text(CONTENT_W - PADDING - copy_w // 2, SPACING["xs"] + copy_h // 2,
                            text="⧉ Копировать", fill=t["text"], font=("Segoe UI", 10, "bold"))

        canvas.create_text(PADDING, SPACING["sm"] + 30, anchor="nw",
                            text="Нажмите Старт или микрофон и продиктуйте…",
                            fill=t["text"], font=("Segoe UI", 12), width=CONTENT_W - PADDING * 2)

    def _build_footer(self, parent, t) -> None:
        ctk.CTkButton(parent, text="Показать плавающий стеклянный островок",
                      fg_color=_mix_hex(t["base"], t["bg"], 0.6), hover_color=_mix_hex(t["accent"], t["bg"], 0.5),
                      text_color=t["text"], corner_radius=self.inner_radius,
                      command=self._open_overlay).pack(fill="x")

    # -- settings sheet (menu -> theme + the settings that don't belong on
    # the main screen) ------------------------------------------------------

    def _close_settings_sheet(self) -> None:
        if self.settings_sheet is not None:
            try:
                self.settings_sheet.destroy()
            except tk.TclError:
                pass
            self.settings_sheet = None

    def _open_settings_sheet(self) -> None:
        self._close_settings_sheet()
        t = self.t
        win = tk.Toplevel(self.root)
        win.title("Настройки")
        win.configure(bg=t["bg"])
        win.geometry(f"360x420+{self.root.winfo_rootx() + 40}+{self.root.winfo_rooty() + 60}")
        win.transient(self.root)
        self.settings_sheet = win

        tk.Label(win, text="ТЕМА ОФОРМЛЕНИЯ", bg=t["bg"], fg=t["muted"],
                font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=SPACING["md"], pady=(SPACING["md"], SPACING["xs"]))
        swatches = tk.Frame(win, bg=t["bg"])
        swatches.pack(anchor="w", padx=SPACING["md"], pady=(0, SPACING["md"]))
        for key in THEME_ORDER:
            th = GLASS_THEMES[key]
            c = tk.Canvas(swatches, width=34, height=34, bg=t["bg"], highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=(0, SPACING["xs"]))
            # Each swatch is rendered in its *own* material, not the active
            # one: three of these palettes differ by material rather than hue,
            # and a row of identically bevelled dots would hide exactly that.
            img = glass_panel(34, 34, min(10, mat(th, "radius")), t["bg"], th["accent"],
                              opacity=min(1.0, 0.9 * mat(th, "tint")),
                              specular=mat(th, "specular"), shade=mat(th, "shade"),
                              rim_light_alpha=mat(th, "rim_light"),
                              rim_dark_alpha=mat(th, "rim_dark"))
            if key == self.theme_key:
                d = ImageDraw.Draw(img)
                d.rounded_rectangle([1, 1, 32, 32], radius=9, outline=(255, 255, 255, 220), width=2)
            self._blit(c, img)
            c.bind("<Button-1>", lambda _e, k=key: self._switch_theme(k))

        rows_frame = tk.Frame(win, bg=t["bg"])
        rows_frame.pack(fill="x", padx=SPACING["md"])
        rows = [
            ("⌨", "Горячая клавиша", "Ctrl + Space — удержание", "switch", True),
            ("🔒", "Отправка отчётов", "Недоступно в этой сборке", "disabled", False),
        ]
        for icon, title, subtitle, kind, on in rows:
            row_h = 56
            row_w = 360 - SPACING["md"] * 2
            canvas = tk.Canvas(rows_frame, width=row_w, height=row_h, bg=t["bg"], highlightthickness=0)
            canvas.pack(fill="x", pady=(0, SPACING["sm"]))
            opacity = 0.16 if kind == "disabled" else 0.32
            row_img = self._panel(row_w, row_h, self.inner_radius, t["base"], opacity)
            self._blit(canvas, row_img)
            text_color = t["muted"] if kind == "disabled" else t["text"]
            canvas.create_text(PADDING, row_h // 2, anchor="w", text=icon, font=("Segoe UI Emoji", 16))
            canvas.create_text(PADDING + 30, row_h // 2 - 9, anchor="w", text=title,
                                fill=text_color, font=("Segoe UI", 12, "bold"))
            canvas.create_text(PADDING + 30, row_h // 2 + 10, anchor="w", text=subtitle,
                                fill=t["muted"], font=("Segoe UI", 10))
            if kind == "switch":
                sw_w, sw_h = 40, 22
                sw_img = self._panel(sw_w, sw_h, min(sw_h // 2, max(2, self.radius)),
                                     t["accent"] if on else t["muted"],
                                     0.85 if on else 0.35)
                self._blit(canvas, sw_img, row_w - PADDING - sw_w, row_h // 2 - sw_h // 2)
                knob_x = row_w - PADDING - 4 - (6 if on else sw_w - 20)
                canvas.create_oval(knob_x, row_h // 2 - 8, knob_x + 16, row_h // 2 + 8, fill="#ffffff", outline="")

        win.bind("<FocusOut>", lambda _e: None)  # kept open on outside click; a real one would close

    # -- floating "Dynamic Island" pill overlay (RULE 7) -------------------

    def _open_overlay(self) -> None:
        if self.overlay is not None:
            try:
                self.overlay.destroy()
            except tk.TclError:
                pass
        t = self.t
        w, h = 320, 64
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.attributes("-topmost", True)
        sw, sh = ov.winfo_screenwidth(), ov.winfo_screenheight()
        ov.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - 160}")
        ov.configure(bg=t["bg"])
        canvas = tk.Canvas(ov, width=w, height=h, bg=t["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        pill = self._panel(w, h, min(h // 2, max(2, self.radius)), t["base"], 0.55)
        self._blit(canvas, pill)

        dot_img = self._lens(28, t["accent"], self._pulse, True)
        self._blit(canvas, dot_img, 16, (h - 28) // 2)

        eq_img = equalizer_image(120, 34, t["accent"], 0.8, self._phase, bars=12)
        self._blit(canvas, eq_img, (w - 120) // 2, (h - 34) // 2)

        stop_img = self._lens(40, "#ff4d6d", 0, False)
        self._blit(canvas, stop_img, w - 56, (h - 40) // 2)
        canvas.create_text(w - 36, h // 2, text="■", fill=t["text"], font=("Segoe UI", 12))
        canvas.create_text(w - 56, h - 8, text="Esc — отмена", fill=t["muted"], font=("Segoe UI", 8))

        canvas.bind("<Button-1>", lambda _e: ov.destroy())
        self.overlay = ov
        self.root.after(30, lambda: round_window_region(ov, w, h, h))

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    LiquidGlassDemo().run()


if __name__ == "__main__":
    main()
