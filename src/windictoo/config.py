"""Persisted user settings."""

from __future__ import annotations

import json
import logging
import os
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
# The onnx-asr backend has no download_root parameter of its own — it goes
# through huggingface_hub, which reads these two variables *at import time*.
# This module is a leaf that every entry point imports before any model
# backend, so setting them here lands early enough. setdefault, not
# assignment: a user who has pointed HF_HUB_CACHE somewhere deliberately
# keeps their choice.
ONNX_MODELS_DIR = MODELS_DIR / "onnx"
os.environ.setdefault("HF_HUB_CACHE", str(ONNX_MODELS_DIR))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
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

    # An id from windictoo.engine.MODELS — the Whisper sizes ("small",
    # "large-v3", ...) plus the onnx entries ("gigaam-v3-ru", "parakeet-v3").
    # An unrecognised value degrades to Whisper small; see engine.spec().
    model: str = "small"
    # Whisper/CTranslate2 only; the onnx models carry their own quantisation.
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

    # How long the microphone stream stays open (see audio.Recorder):
    #   "on_demand" — opened on the hotkey and closed straight after. No idle
    #                 microphone at all, but opening costs 100-400 ms, which
    #                 is exactly the window that swallows the first syllable.
    #   "lazy"      — kept open for `mic_idle_close_sec` after a dictation, so
    #                 back-to-back phrases are instant. The default.
    #   "always"    — opened at startup and never closed. Fastest, but Windows
    #                 shows the microphone-in-use indicator the whole time and
    #                 Bluetooth headsets drop to their low-quality headset
    #                 profile, so this one is opt-in.
    mic_mode: str = "lazy"
    mic_idle_close_sec: int = 30
    # Audio kept from *before* the hotkey went down, so a word begun a moment
    # early still makes it in. Costs 32 KB of RAM at the default.
    preroll_ms: int = 400
    # ...and audio kept after it comes up: people release the key while still
    # finishing the last word.
    tail_ms: int = 200

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

    # One-shot cleanup of autostart leftovers from old app names (VoxWin,
    # WnDic) — only ever useful on a machine upgraded across renames, a
    # dwindling population, so it runs once and never again rather than on
    # every single launch forever.
    legacy_autostart_cleanup_done: bool = False

    def __post_init__(self) -> None:
        # config.json is documented as hand-editable, so a typo here must not
        # reach audio.Recorder (which would silently never close the stream)
        # or the interface (which builds a translation key from this value).
        if self.mic_mode not in ("on_demand", "lazy", "always"):
            log.warning("unknown mic_mode %r, using 'lazy'", self.mic_mode)
            self.mic_mode = "lazy"

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
