"""Persisted user settings."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / "AppData" / "Local" / "WinDictoo"
CONFIG_PATH = CONFIG_DIR / "config.json"
MODELS_DIR = CONFIG_DIR / "models"
LOG_PATH = CONFIG_DIR / "windictoo.log"
# A second launch writes this file to ask the running instance to show its
# window (single-instance handoff), then exits.
SHOW_FLAG = CONFIG_DIR / "show.flag"


@dataclass
class Config:
    # Two keys press easier than three; Ctrl+Space won the field test.
    # (Alt+Space is the Windows system menu, so that one is off the table.)
    hotkey: list[str] = field(default_factory=lambda: ["ctrl", "space"])
    mode: str = "hold"  # "hold" | "toggle"
    # Swallow the hotkey's main key so it doesn't reach the focused app
    # (otherwise holding e.g. Space types spaces / moves the caret).
    suppress_hotkey: bool = True

    model: str = "small"
    compute_type: str = "int8"
    # English default: the project is published for an international
    # audience, not just Russian speakers.
    language: str = "en"  # "auto" | "ru" | "de" | "en"
    threads: int = 4

    refine_enabled: bool = False
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    refine_timeout: float = 20.0

    restore_clipboard: bool = True
    # "type" = SendInput Unicode (caret insert, no clipboard use);
    # "paste" = clipboard + Ctrl+V (more compatible with some apps).
    insertion_method: str = "type"

    onboarding_done: bool = False
    # UI theme: "light-green" (default) or "dark" (violet).
    ui_theme: str = "light-green"

    # Set when the user dismisses an update banner ("Позже") so the same
    # version doesn't nag again on every startup; cleared once they update.
    skipped_update_version: str = ""

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                # "utf-8-sig" tolerates a leading BOM: config.json is meant to
                # be hand-editable (see README), and Notepad/PowerShell save
                # UTF-8 files with a BOM by default, which plain "utf-8" +
                # json.loads() rejects outright.
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
                known = {f for f in cls.__dataclass_fields__}
                return cls(**{k: v for k, v in raw.items() if k in known})
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                log.warning("config.json unreadable (%s), using defaults", exc)
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )
