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
    """Recording was too short or effectively silent.

    `reason` tells the caller which — "short" (held the hotkey too briefly)
    and "silent" (held it plenty long, but the mic delivered nothing) are
    different problems needing different advice, and users have reported
    long, evidently-silent recordings being reported as merely "too short".
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Linear-interpolation resample — not audiophile quality, but Whisper
    doesn't need it, and this matches the resampling this project's own test
    helpers already use for the same 16 kHz target."""
    if from_rate == to_rate or audio.size == 0:
        return audio
    new_len = int(round(len(audio) / from_rate * to_rate))
    if new_len <= 0:
        return np.zeros(0, dtype=np.float32)
    idx = np.linspace(0, len(audio) - 1, new_len)
    return np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)


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
        # _stream_lock serialises the whole of start/stop/cancel against each
        # other. Opening a stream is slow (a device that rejects 16 kHz costs
        # a probe plus a second open — hundreds of ms), and a quick hotkey tap
        # used to land stop() in the middle of that window: _stream was still
        # None, so stop closed nothing, then start finished and assigned a
        # live stream nobody would ever close. Python then collected that
        # orphan while PortAudio still held its callback pointer, and the next
        # audio block jumped into freed memory — an 0xc0000005 access
        # violation reported against "unknown"/_cffi_backend rather than any
        # traceback. Holding this across the entire operation makes a tap
        # simply wait for the open to finish and then close it properly.
        self._stream_lock = threading.RLock()
        self._chunks: list[np.ndarray] = []
        self._peak = 0.0
        self.level = 0.0
        self.is_recording = False
        self._stream_rate = SAMPLE_RATE
        # device -> sample rate known to work, so the 16 kHz attempt that this
        # device already rejected is not repeated on every single recording.
        self._rate_cache: dict[object, int] = {}

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
        with self._stream_lock:
            if self.is_recording or self._stream is not None:
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
            opened: tuple[sd.InputStream, int] | None = None
            used_dev: int | None = None
            for i, dev in enumerate(candidates):
                try:
                    opened = self._open_stream(dev)
                    used_dev = dev
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if i < len(candidates) - 1:
                        log.warning("input device %s failed (%s), trying next", dev, exc)
            if last_exc is not None or opened is None:
                # Clear the flag before propagating: leaving it set made every
                # later start() return early at the guard above, so a single
                # failed open disabled dictation until the app was restarted.
                with self._lock:
                    self.is_recording = False
                raise last_exc if last_exc is not None else RuntimeError("no input device")
            self._stream, self._stream_rate = opened
            log.info("recording started (device=%s, rate=%d)", used_dev, self._stream_rate)

    def _make_stream(self, device: int | None, rate: int) -> sd.InputStream:
        stream = sd.InputStream(
            samplerate=rate, channels=1, dtype="float32",
            blocksize=1024, device=device, callback=self._callback,
        )
        stream.start()
        return stream

    def _open_stream(self, device: int | None) -> tuple[sd.InputStream, int]:
        """Try `device` at our target 16 kHz first; WASAPI devices commonly
        reject any rate but their own mix format ("Invalid sample rate"),
        which was previously caught only to fall straight back to the
        legacy MME host API — silently defeating the whole point of
        preferring WASAPI (see _preferred_input_device) on every single
        recording. Retrying at the device's own native rate keeps the
        stream on WASAPI; _teardown() resamples the result back to 16 kHz.

        The working rate is remembered per device. Re-probing 16 kHz on a
        device already known to refuse it cost a failed open plus a query on
        every recording — hundreds of milliseconds of latency, and exactly
        the window in which a quick hotkey tap used to strand a stream."""
        cached = self._rate_cache.get(device)
        if cached is not None:
            try:
                return self._make_stream(device, cached), cached
            except Exception as exc:  # noqa: BLE001
                # Mix format can change (headset swap, Windows audio settings);
                # forget it and fall through to the full probe below.
                log.info("device %s no longer accepts cached %d Hz (%s); re-probing",
                         device, cached, exc)
                self._rate_cache.pop(device, None)

        try:
            stream = self._make_stream(device, SAMPLE_RATE)
            self._rate_cache[device] = SAMPLE_RATE
            return stream, SAMPLE_RATE
        except Exception as exc:  # noqa: BLE001
            native_rate = None
            if device is not None:
                try:
                    native_rate = int(round(sd.query_devices(device)["default_samplerate"]))
                except Exception:  # noqa: BLE001
                    native_rate = None
            if native_rate is None or native_rate == SAMPLE_RATE:
                raise
            log.info("device %s rejected %d Hz (%s); retrying at its native %d Hz",
                      device, SAMPLE_RATE, exc, native_rate)
            stream = self._make_stream(device, native_rate)
            self._rate_cache[device] = native_rate
            return stream, native_rate

    def _teardown(self) -> np.ndarray:
        # Held for the whole teardown so it cannot interleave with an
        # in-progress start(); see the _stream_lock comment in __init__.
        with self._stream_lock:
            with self._lock:
                self.is_recording = False
            stream, self._stream = self._stream, None
            if stream is not None:
                # Always close explicitly. Dropping the last reference and
                # letting the garbage collector do it is what turns a stray
                # stream into a native crash: PortAudio keeps calling the
                # callback the collector has already freed.
                try:
                    stream.stop()
                finally:
                    stream.close()
            with self._lock:
                chunks = self._chunks
                self._chunks = []
                self.level = 0.0
            audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
            return _resample(audio, self._stream_rate, SAMPLE_RATE)

    def stop(self) -> np.ndarray:
        """Return captured audio, or raise EmptyRecording.

        A very quick tap blocks here until an in-flight start() has finished
        opening its stream, so the stream is closed rather than stranded.
        """
        audio = self._teardown()
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION:
            log.info(
                "recording rejected as too short (%.2fs, peak %.3f)", duration, self._peak
            )
            raise EmptyRecording("short")
        if self._peak < MIN_PEAK:
            # Long enough to be a real attempt, but not a whisper of signal —
            # this is "the microphone isn't picking anything up", not "you
            # let go too fast". Conflating the two produced a confusing
            # "recording too short" message after a 78-second silent hold.
            log.info(
                "recording rejected as silent (%.2fs, peak %.3f)", duration, self._peak
            )
            raise EmptyRecording("silent")
        log.info("recording stopped (%.2fs)", duration)
        return audio

    def cancel(self) -> None:
        with self._stream_lock:
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
