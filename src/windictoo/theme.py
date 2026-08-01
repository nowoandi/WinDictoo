"""Shared visual palette for the CustomTkinter UI.

Several themes: the original dark (violet accent), and a handful of calm
light palettes (mint green, dusty rose, light blue, chocolate+gold).
`apply(name)` swaps the module-level colours; the GUI rebuilds itself so
the change is live.
"""

from __future__ import annotations

from .app import State

# Names of the module-level colour attributes a palette provides.
_KEYS = ("BG", "CARD", "CARD_HI", "STROKE", "TEXT", "MUTED", "ACCENT",
         "ACCENT_HOVER", "ACCENT_DIM", "ON_ACCENT", "SUCCESS", "WARN", "DANGER", "STATE_COLOR")

PALETTES: dict[str, dict] = {
    "dark": {
        "BG": "#141420", "CARD": "#1e1e2c", "CARD_HI": "#262636", "STROKE": "#2f2f42",
        "TEXT": "#ececf4", "MUTED": "#9a9ab0",
        "ACCENT": "#6c5ce7", "ACCENT_HOVER": "#5a4bd4", "ACCENT_DIM": "#3a3560",
        "ON_ACCENT": "#ffffff",
        "SUCCESS": "#3ddc84", "WARN": "#ffb020", "DANGER": "#ff4d6d",
        "APPEARANCE": "dark",
        "STATE_COLOR": {
            State.IDLE: "#6c5ce7", State.RECORDING: "#ff4d6d", State.TRANSCRIBING: "#4aa3ff",
            State.REFINING: "#a06bff", State.INSERTING: "#4aa3ff", State.DONE: "#3ddc84",
            State.CANCELLED: "#9a9ab0", State.ERROR: "#ffb020",
        },
    },
    "geek-black": {
        # True-black, neon-green-on-black "hacker terminal" look.
        "BG": "#000000", "CARD": "#0a0f0c", "CARD_HI": "#10160f", "STROKE": "#1f2b22",
        "TEXT": "#d7ffe0", "MUTED": "#6fae7f",
        "ACCENT": "#39ff14", "ACCENT_HOVER": "#2ecc0f", "ACCENT_DIM": "#143d16",
        # White-on-neon-green is nearly unreadable — every other theme's
        # ACCENT is dark/saturated enough for white text, this one isn't.
        "ON_ACCENT": "#062b0c",
        "SUCCESS": "#39ff14", "WARN": "#ffb020", "DANGER": "#ff3b3b",
        "APPEARANCE": "dark",
        "STATE_COLOR": {
            State.IDLE: "#39ff14", State.RECORDING: "#ff3b3b", State.TRANSCRIBING: "#22d3ee",
            State.REFINING: "#a06bff", State.INSERTING: "#22d3ee", State.DONE: "#39ff14",
            State.CANCELLED: "#6fae7f", State.ERROR: "#ffb020",
        },
    },
    "light-green": {
        # Airy mint base with crisp white cards floating on it.
        "BG": "#e6f3ea", "CARD": "#ffffff", "CARD_HI": "#eef7f1", "STROKE": "#cfe4d6",
        # MUTED darkened from #41604e: secondary labels were hard to read on
        # the white cards (user feedback).
        "TEXT": "#123021", "MUTED": "#2a4a38",
        "ACCENT": "#0f9e51", "ACCENT_HOVER": "#0b7c3e", "ACCENT_DIM": "#bfe6cd",
        "ON_ACCENT": "#ffffff",
        "SUCCESS": "#0f9e51", "WARN": "#c9761a", "DANGER": "#dd3d74",
        "APPEARANCE": "light",
        "STATE_COLOR": {
            State.IDLE: "#0f9e51", State.RECORDING: "#dd3d74", State.TRANSCRIBING: "#0284c7",
            State.REFINING: "#6d4bd8", State.INSERTING: "#0284c7", State.DONE: "#0f9e51",
            State.CANCELLED: "#6b8577", State.ERROR: "#c9761a",
        },
    },
    "light-blue": {
        # Same airy structure as light-green, cool tone instead of mint.
        "BG": "#e7eff5", "CARD": "#ffffff", "CARD_HI": "#eef5fa", "STROKE": "#cfe0ea",
        "TEXT": "#0f2733", "MUTED": "#3d5866",
        "ACCENT": "#1f7a9e", "ACCENT_HOVER": "#175f7a", "ACCENT_DIM": "#c3e0ea",
        "ON_ACCENT": "#ffffff",
        "SUCCESS": "#0f9e51", "WARN": "#c9761a", "DANGER": "#dd3d74",
        "APPEARANCE": "light",
        "STATE_COLOR": {
            State.IDLE: "#1f7a9e", State.RECORDING: "#dd3d74", State.TRANSCRIBING: "#1f7a9e",
            State.REFINING: "#6d4bd8", State.INSERTING: "#1f7a9e", State.DONE: "#0f9e51",
            State.CANCELLED: "#6b8290", State.ERROR: "#c9761a",
        },
    },
    "dusty-rose": {
        # "Альтроза" — calm, warm rose instead of mint/blue.
        "BG": "#f5e8ea", "CARD": "#ffffff", "CARD_HI": "#faf0f1", "STROKE": "#e3cdd1",
        "TEXT": "#3d1f24", "MUTED": "#6b4750",
        "ACCENT": "#b5657a", "ACCENT_HOVER": "#9c4f62", "ACCENT_DIM": "#ecd3d8",
        "ON_ACCENT": "#ffffff",
        "SUCCESS": "#4a9d6f", "WARN": "#c9761a", "DANGER": "#c0435a",
        "APPEARANCE": "light",
        "STATE_COLOR": {
            State.IDLE: "#b5657a", State.RECORDING: "#c0435a", State.TRANSCRIBING: "#3a7fa8",
            State.REFINING: "#8a5a9c", State.INSERTING: "#3a7fa8", State.DONE: "#4a9d6f",
            State.CANCELLED: "#8c6b71", State.ERROR: "#c9761a",
        },
    },
    "choc-gold": {
        # Draft — colours lifted from the Event Deko Schneider brand board
        # (cream/near-black/gold) the user shared; swap in their exact link
        # once sent, this is a starting point to react to, not final.
        "BG": "#faf7f2", "CARD": "#ffffff", "CARD_HI": "#f3ede3", "STROKE": "#e8e0d4",
        "TEXT": "#1a1410", "MUTED": "#6b5c4d",
        "ACCENT": "#b8935a", "ACCENT_HOVER": "#9c7a45", "ACCENT_DIM": "#e8dcc4",
        # White measured only 2.85:1 on this soft gold — below the AA-large
        # floor. A very dark brown keeps the palette warm and reaches 7.4:1.
        "ON_ACCENT": "#231a09",
        "SUCCESS": "#7a9456", "WARN": "#c9761a", "DANGER": "#a8433a",
        "APPEARANCE": "light",
        "STATE_COLOR": {
            State.IDLE: "#b8935a", State.RECORDING: "#a8433a", State.TRANSCRIBING: "#8a6a3a",
            State.REFINING: "#8a6aa0", State.INSERTING: "#8a6a3a", State.DONE: "#7a9456",
            State.CANCELLED: "#8c7d6a", State.ERROR: "#c9761a",
        },
    },
}

# Canonical theme order for the swatch picker. The picker itself shows no
# text (just each theme's ACCENT colour as a little square) — this dict's
# values are a fallback label (tooltips, logs) rather than UI copy.
THEME_LABELS: dict[str, str] = {
    "dark": "Тёмная",
    "geek-black": "Гик-чёрная",
    "light-green": "Светло-зелёная",
    "light-blue": "Светло-синяя",
    "dusty-rose": "Альтроза",
    "choc-gold": "Шоколад-золото",
}

# Live values (default dark) — set by apply().
BG = CARD = CARD_HI = STROKE = TEXT = MUTED = ACCENT = ACCENT_HOVER = ACCENT_DIM = ""
ON_ACCENT = ""
SUCCESS = WARN = DANGER = ""
APPEARANCE = "dark"
STATE_COLOR: dict[State, str] = {}
name = "dark"

# Corner radius design tokens for consistent UI hierarchy
RADIUS_CONTAINER = 16  # Hero cards, main result card, onboarding main card
RADIUS_CARD = 12       # Secondary section cards, tabview, floating overlay
RADIUS_WIDGET = 10     # Text box, option menus, text fields, inputs
RADIUS_BUTTON = 12     # Action buttons (Start/Stop, Copy, Hotkey, dialog buttons)
RADIUS_CHIP = 10       # Information status chips


def apply(theme_name: str) -> str:
    """Set the module-level colours to the chosen palette; returns its name."""
    global name, APPEARANCE
    p = PALETTES.get(theme_name, PALETTES["dark"])
    g = globals()
    for k in _KEYS:
        g[k] = p[k]
    APPEARANCE = p["APPEARANCE"]
    name = theme_name if theme_name in PALETTES else "dark"
    return name


# --------------------------------------------------------------- contrast
# Six palettes x every accent surface is too much to eyeball reliably — a
# label that reads fine on the violet accent can be invisible on neon green
# (that combination measured 1.06:1 before this existed, i.e. no contrast at
# all). These let a call site *ask* for a readable colour instead of
# hard-coding one per palette, so adding a palette can't silently reintroduce
# an unreadable pair.

AA_LARGE = 3.0  # WCAG AA threshold for large/bold UI text


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG relative-contrast ratio between two hex colours (1.0 .. 21.0)."""
    try:
        lf, lb = _luminance(fg), _luminance(bg)
    except (ValueError, IndexError):
        return 1.0
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(bg: str, *candidates: str) -> str:
    """First candidate that clears AA_LARGE against `bg`, else whichever
    contrasts most. Callers pass their preferred (on-brand) colour first and
    a safe fallback last, so the tint is kept wherever it's actually legible."""
    usable = [c for c in candidates if isinstance(c, str) and c.startswith("#")]
    if not usable:
        return TEXT
    for c in usable:
        if contrast_ratio(c, bg) >= AA_LARGE:
            return c
    return max(usable, key=lambda c: contrast_ratio(c, bg))


apply("dark")

# Text labels for states live in windictoo.i18n (state_label/tray_label) so
# they follow Config.ui_language; only the language-neutral glyphs stay here.
STATE_GLYPH: dict[State, str] = {
    State.IDLE: "🎙",
    State.RECORDING: "🎙",
    State.TRANSCRIBING: "✍",
    State.REFINING: "✨",
    State.INSERTING: "⌨",
    State.DONE: "✓",
    State.CANCELLED: "✕",
    State.ERROR: "!",
}
