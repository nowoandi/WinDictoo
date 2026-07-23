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


def _preferred_input_device() -> int | None:
    """Prefer the WASAPI host API's default input device over whatever
    PortAudio picks as the overall default — which on Windows is usually the
    legacy MME host API. MME's native callback trampoline has been observed
    to segfault (0xc0000005 inside _cffi_backend) when a Bluetooth headset
    changes profile or briefly drops out mid-stream; WASAPI is Microsoft's
    modern audio stack and does not share that failure mode. Falls back to
    None (PortAudio's own default) if WASAPI is unavailable."""
    try:
        hostapis = sd.query_hostapis()
        wasapi = next((h for h in hostapis if h["name"] == "Windows WASAPI"), None)
        if wasapi is None:
            return None
        idx = wasapi["default_input_device"]
        return idx if idx >= 0 else None
    except Exception:  # noqa: BLE001
        return None


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

    def start(self, device: int | None = None) -> None:
        """`device` overrides the user's saved microphone choice (see
        Config.input_device_index); None means "system default"."""
        if self.is_recording:
            return
        with self._lock:
            self._chunks = []
            self._peak = 0.0
            self.level = 0.0
            self.is_recording = True

        # Fallback chain: the user's chosen device, then WASAPI's own
        # default, then whatever PortAudio itself considers default — each
        # a little less specific, so a disconnected/renumbered device never
        # hard-fails the whole session.
        candidates: list[int | None] = []
        if device is not None:
            candidates.append(device)
        preferred = _preferred_input_device()
        if preferred is not None and preferred not in candidates:
            candidates.append(preferred)
        candidates.append(None)

        last_exc: Exception | None = None
        for i, dev in enumerate(candidates):
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                    device=dev,
                    callback=self._callback,
                )
                self._stream.start()
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if i < len(candidates) - 1:
                    log.warning("input device %s failed (%s), trying next", dev, exc)
        if last_exc is not None:
            raise last_exc
        log.info("recording started (device=%s)", dev)

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
    """WASAPI-hosted input devices only — the host API this app always
    prefers (see _preferred_input_device). Without this filter the same
    physical microphone shows up to four times, once per legacy host API
    (MME/DirectSound/WDM-KS), which only confuses a device picker."""
    try:
        hostapis = sd.query_hostapis()
        wasapi_idx = next(
            (i for i, h in enumerate(hostapis) if h["name"] == "Windows WASAPI"), None
        )
    except Exception:  # noqa: BLE001
        wasapi_idx = None
    return [
        (i, d["name"])
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0 and (wasapi_idx is None or d["hostapi"] == wasapi_idx)
    ]
