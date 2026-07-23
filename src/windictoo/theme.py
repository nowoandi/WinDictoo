"""Shared visual palette for the CustomTkinter UI.

Two themes: the original dark (violet accent) and a light-green one that
mirrors the airy landing-page look. `apply(name)` swaps the module-level
colours; the GUI rebuilds itself so the change is live.
"""

from __future__ import annotations

from .app import State

# Names of the module-level colour attributes a palette provides.
_KEYS = ("BG", "CARD", "CARD_HI", "STROKE", "TEXT", "MUTED", "ACCENT",
         "ACCENT_HOVER", "ACCENT_DIM", "SUCCESS", "WARN", "DANGER", "STATE_COLOR")

PALETTES: dict[str, dict] = {
    "dark": {
        "BG": "#141420", "CARD": "#1e1e2c", "CARD_HI": "#262636", "STROKE": "#2f2f42",
        "TEXT": "#ececf4", "MUTED": "#9a9ab0",
        "ACCENT": "#6c5ce7", "ACCENT_HOVER": "#5a4bd4", "ACCENT_DIM": "#3a3560",
        "SUCCESS": "#3ddc84", "WARN": "#ffb020", "DANGER": "#ff4d6d",
        "APPEARANCE": "dark",
        "STATE_COLOR": {
            State.IDLE: "#6c5ce7", State.RECORDING: "#ff4d6d", State.TRANSCRIBING: "#4aa3ff",
            State.REFINING: "#a06bff", State.INSERTING: "#4aa3ff", State.DONE: "#3ddc84",
            State.CANCELLED: "#9a9ab0", State.ERROR: "#ffb020",
        },
    },
    "light-green": {
        # Airy mint base with crisp white cards floating on it.
        "BG": "#e6f3ea", "CARD": "#ffffff", "CARD_HI": "#eef7f1", "STROKE": "#cfe4d6",
        # MUTED darkened from #41604e: secondary labels were hard to read on
        # the white cards (user feedback).
        "TEXT": "#123021", "MUTED": "#2a4a38",
        "ACCENT": "#0f9e51", "ACCENT_HOVER": "#0b7c3e", "ACCENT_DIM": "#bfe6cd",
        "SUCCESS": "#0f9e51", "WARN": "#c9761a", "DANGER": "#dd3d74",
        "APPEARANCE": "light",
        "STATE_COLOR": {
            State.IDLE: "#0f9e51", State.RECORDING: "#dd3d74", State.TRANSCRIBING: "#0284c7",
            State.REFINING: "#6d4bd8", State.INSERTING: "#0284c7", State.DONE: "#0f9e51",
            State.CANCELLED: "#6b8577", State.ERROR: "#c9761a",
        },
    },
}

# Live values (default dark) — set by apply().
BG = CARD = CARD_HI = STROKE = TEXT = MUTED = ACCENT = ACCENT_HOVER = ACCENT_DIM = ""
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


apply("dark")

STATE_LABEL: dict[State, str] = {
    State.IDLE: "Готов к диктовке",
    State.RECORDING: "Слушаю…",
    State.TRANSCRIBING: "Распознаю…",
    State.REFINING: "Улучшаю текст…",
    State.INSERTING: "Вставляю…",
    State.DONE: "Готово",
    State.CANCELLED: "Отменено",
    State.ERROR: "Ошибка",
}

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
