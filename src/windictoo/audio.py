"""Microphone capture into a 16 kHz mono float32 buffer for Whisper."""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Below this, Whisper has nothing usable: a mis-tap or a dead microphone.
MIN_DURATION = 0.35
MIN_PEAK = 0.005


class EmptyRecording(Exception):
    """Recording was too short or effectively silent."""


class Recorder:
    def __init__(self) -> None:
        self._stream: sd.InputStream | None = None
        # _lock guards _chunks/_peak: the PortAudio callback runs on its own
        # thread while start/stop/cancel are called from the hotkey thread.
        self._lock = threading.Lock()
        self._chunks: list[np.ndarray] = []
        self._peak = 0.0
        self.level = 0.0
        self.is_recording = False

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("audio status: %s", status)
        with self._lock:
            if not self.is_recording:
                return
            block = indata[:, 0].copy()
            self._chunks.append(block)
            rms = float(np.sqrt(np.mean(block**2))) if block.size else 0.0
            self.level = min(1.0, rms * 18)
            self._peak = max(self._peak, self.level)

    def start(self) -> None:
        if self.is_recording:
            return
        with self._lock:
            self._chunks = []
            self._peak = 0.0
            self.level = 0.0
            self.is_recording = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=self._callback,
        )
        self._stream.start()
        log.info("recording started")

    def _teardown(self) -> np.ndarray:
        with self._lock:
            self.is_recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            chunks = self._chunks
            self._chunks = []
            self.level = 0.0
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def stop(self) -> np.ndarray:
        """Return captured audio, or raise EmptyRecording."""
        audio = self._teardown()
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION or self._peak < MIN_PEAK:
            log.info(
                "recording rejected as empty (%.2fs, peak %.3f)", duration, self._peak
            )
            raise EmptyRecording
        log.info("recording stopped (%.2fs)", duration)
        return audio

    def cancel(self) -> None:
        if not self.is_recording and self._stream is None:
            return
        self._teardown()
        log.info("recording cancelled")


def input_devices() -> list[tuple[int, str]]:
    return [
        (i, d["name"])
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]
