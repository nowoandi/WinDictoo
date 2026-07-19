"""Local speech-to-text via faster-whisper (CTranslate2, CPU/int8)."""

from __future__ import annotations

import logging
import re
import threading

import numpy as np

from .config import MODELS_DIR, Config

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
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                MODELS_DIR.mkdir(parents=True, exist_ok=True)
                log.info(
                    "loading model %s (%s, %d threads)",
                    self.cfg.model,
                    self.cfg.compute_type,
                    self.cfg.threads,
                )
                self._model = WhisperModel(
                    self.cfg.model,
                    device="cpu",
                    compute_type=self.cfg.compute_type,
                    cpu_threads=self.cfg.threads,
                    download_root=str(MODELS_DIR),
                )
                log.info("model loaded")
            return self._model

    def transcribe(self, audio: np.ndarray) -> tuple[str, str | None]:
        """Return (text, detected_language)."""
        model = self.load()
        language = None if self.cfg.language == "auto" else self.cfg.language
        segments, info = model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        raw = "".join(s.text for s in segments)
        text = normalize_whitespace(strip_artifacts(raw))
        detected = getattr(info, "language", None)
        log.info("transcribed %d chars (lang=%s)", len(text), detected)
        return text, detected
