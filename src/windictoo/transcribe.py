"""Local speech-to-text.

The actual recognition lives in windictoo.engine (faster-whisper for the
Whisper sizes, onnx-asr for GigaAM and Parakeet). What stays here is
everything that is the same whichever backend ran: lazy loading, the idle
unload timer, and scrubbing the non-speech annotations every ASR model emits
sooner or later.
"""

from __future__ import annotations

import logging
import re
import threading

import numpy as np

from . import engine
from .config import Config

log = logging.getLogger(__name__)

# Square-bracket annotations are never real dictation output.
_BRACKET = re.compile(r"\[[^\]\n]{0,60}\]")
_PAREN_MARKERS = (
    "music|applause|laughter|typing|silence|inaudible|noise|coughing|sighs?|beep"
    "|музыка|аплодисменты|смех|тишина|шум|неразборчиво|вздох|кашель"
    "|musik|applaus|lachen|stille|geräusch"
)
_PAREN = re.compile(rf"\((?:{_PAREN_MARKERS})[^)\n]{{0,20}}\)", re.IGNORECASE)


def strip_artifacts(text: str) -> str:
    text = _BRACKET.sub(" ", text)
    text = _PAREN.sub(" ", text)
    return text.replace("♪", " ")


def normalize_whitespace(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


class Transcriber:
    """Lazily loads the model; the first call pays the load cost."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.spec = engine.spec(cfg.model)
        self._engine = engine.make(cfg, self.spec)
        self._loaded = False
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None
        # (megabytes on disk, megabytes expected) while a load is running,
        # None otherwise. Read by the interface to draw a progress bar; a
        # first run downloads 216 MB to 3 GB depending on the model, and
        # without this the app simply sits there looking broken.
        self.progress: tuple[float, float] | None = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self):
        self._cancel_unload_timer()
        with self._lock:
            if not self._loaded:
                stop = threading.Event()
                # Every path into the model — startup preload, the Settings
                # button, and the first dictation after a model change — goes
                # through here, so watching it here means all three report.
                self.progress = (0.0, float(self.spec.size_mb))
                watcher = threading.Thread(
                    target=self._watch_download, args=(stop,), daemon=True)
                watcher.start()
                try:
                    self._engine.load()
                    self._loaded = True
                finally:
                    stop.set()
                    self.progress = None
            return self._engine

    def _watch_download(self, stop: threading.Event) -> None:
        total = float(self.spec.size_mb)
        while not stop.wait(0.3):
            done = engine.bytes_on_disk(self.spec) / 1_000_000
            self.progress = (min(done, total), total)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str | None]:
        """Return (text, detected_language)."""
        self.load()
        raw, detected = self._engine.transcribe(audio)
        text = normalize_whitespace(strip_artifacts(raw))
        log.info("transcribed %d chars (lang=%s)", len(text), detected)
        self._schedule_unload()
        return text, detected

    # ------------------------------------------------------------- idle unload

    def _schedule_unload(self) -> None:
        """Free the model (~0.2-3 GB depending on size) after N minutes of
        no dictation, for users on low-RAM machines. Opt-in via
        Config.unload_model_idle_min (0 = never); each new transcription
        resets the timer via load()'s _cancel_unload_timer()."""
        self._cancel_unload_timer()
        minutes = self.cfg.unload_model_idle_min
        if not minutes:
            return
        self._unload_timer = threading.Timer(minutes * 60, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _cancel_unload_timer(self) -> None:
        if self._unload_timer is not None:
            self._unload_timer.cancel()
            self._unload_timer = None

    def _unload(self) -> None:
        with self._lock:
            if self._loaded:
                # Dropping the engine drops the only reference to the loaded
                # weights; a fresh one is built so the next load() works.
                self._engine = engine.make(self.cfg, self.spec)
                self._loaded = False
                log.info("model unloaded after %d min idle", self.cfg.unload_model_idle_min)
