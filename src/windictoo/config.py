"""Persisted user settings."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Whisper language codes this app's language picker actually offers
# (windictoo.gui.LANGS) — kept in sync manually since gui.py can't be
# imported from here without a circular import.
_SUPPORTED_LANGS = {"ru", "en", "de", "fr", "es", "zh", "tr", "hy"}


def _detect_system_language() -> str:
    """The Windows UI locale, if it's one we support — used only as the
    *default* for a brand-new install (an existing config.json always wins;
    see Config.load()). GetUserDefaultLocaleName is a plain Win32 API call,
    no special permissions or dialogs involved. Falls back to English on
    any failure or on a locale we don't have a picker entry for."""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
            code = buf.value.split("-")[0].lower()
            if code in _SUPPORTED_LANGS:
                return code
    except Exception:  # noqa: BLE001
        pass
    return "en"


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

    # None = system default (WASAPI), else a specific sounddevice index from
    # audio.input_devices(). Indices aren't stable across reboots/USB
    # replugs on every system, so treat a stale value as "device gone" and
    # fall back rather than raising (Recorder.start() already does this).
    input_device_index: int | None = None

    model: str = "small"
    compute_type: str = "int8"
    # Defaults to the Windows UI language on a brand-new install (falls back
    # to English if that's not one of our supported codes); once saved, the
    # user's own choice always takes over — see _detect_system_language().
    language: str = field(default_factory=_detect_system_language)
    threads: int = 4

    # Interface language (buttons/labels/dialogs) — deliberately independent
    # from `language` above (which only controls what Whisper transcribes).
    # Same system-locale default, but the two are separate settings so a
    # dictation language change never silently changes the app's own text.
    ui_language: str = field(default_factory=_detect_system_language)

    # 0 = keep the model in RAM forever (fastest repeat dictation); >0 =
    # unload it after that many idle minutes to free RAM on weaker PCs.
    unload_model_idle_min: int = 0

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
