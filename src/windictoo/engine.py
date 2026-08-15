"""Speech-to-text backends and the catalogue of models the app offers.

Two backends sit behind one interface:

* **faster-whisper** (CTranslate2) — the original engine. 99 languages, and
  the only one that lets the user *pick* the spoken language.
* **onnx-asr** (onnxruntime) — GigaAM v3 for Russian and Parakeet TDT v3 for
  25 European languages. Both are markedly faster on CPU than Whisper at
  comparable or better accuracy, and both already emit punctuation and
  capitalisation, which is what makes them usable for dictation at all
  (the plain `gigaam-v3-rnnt` variant returns bare lowercase words — the
  `e2e` variants are the ones with punctuation, hence the ids below).

onnxruntime is already a faster-whisper dependency — it runs Silero VAD —
so the second backend costs the packaged build essentially nothing.

Neither onnx model takes a language argument: GigaAM is Russian-only and
Parakeet detects the language itself. `ModelSpec.honors_language` records
that, so the interface can grey out the picker instead of silently ignoring
what the user chose.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .config import MODELS_DIR, ONNX_MODELS_DIR, Config

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000

WHISPER = "whisper"
ONNX = "onnx"

# The 25 European languages Parakeet TDT 0.6B v3 was trained on. Only the
# overlap with the app's own picker (windictoo.gui.LANGS) is ever shown, but
# the full set is what decides whether a language is supported at all.
_PARAKEET_LANGS = (
    "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de", "el", "hu",
    "it", "lv", "lt", "mt", "pl", "pt", "ro", "ru", "sk", "sl", "es", "sv", "uk",
)


@dataclass(frozen=True)
class ModelSpec:
    """One entry in the model picker.

    `id` is what lands in config.json; `backend` is what the backend itself
    calls the model. They differ for the onnx entries so the config stays
    readable ("gigaam-v3-ru") and stable if we ever switch variant.
    """

    id: str
    engine: str
    backend: str
    title: str
    size_mb: int
    # Languages the model can transcribe; None means "every Whisper language".
    langs: tuple[str, ...] | None
    # False when the model ignores Config.language (picks or fixes it itself).
    honors_language: bool
    quantization: str | None = None

    def supports(self, lang: str) -> bool:
        """`lang` is a Whisper-style code, or "auto"."""
        if self.langs is None:
            return True
        if lang == "auto":
            # Only meaningful for a model that detects on its own; a
            # single-language model is trivially "auto" too.
            return True
        return lang in self.langs

    @property
    def fixed_language(self) -> str | None:
        """The one language this model always transcribes, if it has one."""
        if self.langs is not None and len(self.langs) == 1:
            return self.langs[0]
        return None


MODELS: tuple[ModelSpec, ...] = (
    ModelSpec("tiny", WHISPER, "tiny", "Whisper tiny", 75, None, True),
    ModelSpec("base", WHISPER, "base", "Whisper base", 145, None, True),
    ModelSpec("small", WHISPER, "small", "Whisper small", 485, None, True),
    ModelSpec("medium", WHISPER, "medium", "Whisper medium", 1500, None, True),
    ModelSpec("large-v3", WHISPER, "large-v3", "Whisper large-v3", 3000, None, True),
    ModelSpec(
        "gigaam-v3-ru", ONNX, "gigaam-v3-e2e-rnnt", "GigaAM v3",
        216, ("ru",), False, quantization="int8",
    ),
    ModelSpec(
        "parakeet-v3", ONNX, "nemo-parakeet-tdt-0.6b-v3", "Parakeet v3",
        639, _PARAKEET_LANGS, False, quantization="int8",
    ),
)

_BY_ID = {m.id: m for m in MODELS}

DEFAULT_MODEL = "small"


def spec(model_id: str) -> ModelSpec:
    """The catalogue entry for `model_id`, falling back to the default.

    A config written by a newer build (or hand-edited, which the README
    invites) must not brick dictation, so an unknown id degrades to Whisper
    small rather than raising.
    """
    found = _BY_ID.get(model_id)
    if found is None:
        log.warning("unknown model %r, falling back to %s", model_id, DEFAULT_MODEL)
        return _BY_ID[DEFAULT_MODEL]
    return found


def models_for(lang: str) -> tuple[ModelSpec, ...]:
    """Catalogue entries able to handle `lang`."""
    return tuple(m for m in MODELS if m.supports(lang))


# --------------------------------------------------------------------- engines


class Engine(Protocol):
    """What Transcriber needs from a backend."""

    def load(self) -> None:
        """Fetch and initialise the model. Slow; safe to call repeatedly."""

    def transcribe(self, audio: np.ndarray) -> tuple[str, str | None]:
        """Return (raw text, detected language or None) for 16 kHz mono float32."""


class FasterWhisperEngine:
    def __init__(self, cfg: Config, model: ModelSpec) -> None:
        self.cfg = cfg
        self.model = model
        self._impl = None

    def load(self) -> None:
        if self._impl is not None:
            return
        from faster_whisper import WhisperModel

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        log.info(
            "loading %s (%s, %d threads)",
            self.model.backend, self.cfg.compute_type, self.cfg.threads,
        )
        self._impl = WhisperModel(
            self.model.backend,
            device="cpu",
            compute_type=self.cfg.compute_type,
            cpu_threads=self.cfg.threads,
            download_root=str(MODELS_DIR),
        )
        log.info("model loaded")

    def transcribe(self, audio: np.ndarray) -> tuple[str, str | None]:
        self.load()
        language = None if self.cfg.language == "auto" else self.cfg.language
        segments, info = self._impl.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return "".join(s.text for s in segments), getattr(info, "language", None)


class OnnxAsrEngine:
    def __init__(self, cfg: Config, model: ModelSpec) -> None:
        self.cfg = cfg
        self.model = model
        self._impl = None

    def load(self) -> None:
        if self._impl is not None:
            return
        import onnx_asr
        import onnxruntime

        ONNX_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        # Honour the same thread slider Whisper uses; onnxruntime otherwise
        # helps itself to every core, which makes dictation fight the
        # foreground app for CPU on a laptop.
        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = self.cfg.threads
        log.info(
            "loading %s (%s, %d threads)",
            self.model.backend, self.model.quantization or "float32", self.cfg.threads,
        )
        self._impl = onnx_asr.load_model(
            self.model.backend,
            quantization=self.model.quantization,
            sess_options=opts,
        )
        log.info("model loaded")

    def transcribe(self, audio: np.ndarray) -> tuple[str, str | None]:
        self.load()
        # No language argument: onnx-asr only accepts one for Whisper and
        # Canary models, and neither of ours is either (see module docstring).
        text = self._impl.recognize(audio, sample_rate=SAMPLE_RATE)
        return text, self.model.fixed_language


def make(cfg: Config, model: ModelSpec) -> Engine:
    if model.engine == ONNX:
        return OnnxAsrEngine(cfg, model)
    return FasterWhisperEngine(cfg, model)
