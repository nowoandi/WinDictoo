"""Microphone capture into a 16 kHz mono float32 buffer for Whisper.

The stream is *not* tied to the hotkey. Opening a capture device costs
100-400 ms — a WASAPI device that refuses 16 kHz costs a failed open plus a
query on top — and that delay used to land squarely on the first syllable of
every dictation. So the stream is opened once and kept running: while no
dictation is in progress its blocks go into a small ring buffer (Config
.preroll_ms, 400 ms by default, about 32 KB), and pressing the hotkey simply
starts appending to a recording buffer that has been *pre-seeded with the
ring*. A word begun a moment before the key went down is therefore already
captured. Config.tail_ms does the same at the other end, for the very common
habit of releasing the key while still finishing the last word.

How long the stream lingers is Config.mic_mode — see the comment on that
field. The default keeps it open for half a minute after a dictation, which
makes back-to-back phrases instant without holding the microphone open (and
the Windows in-use indicator lit) all day.

A consequence worth knowing: "recording too short" can no longer be decided
from the length of the buffer, because the pre-roll always makes it at least
preroll_ms long. It is decided from how long the key was actually held.
"""

from __future__ import annotations

import collections
import logging
import threading
import time

import numpy as np
import sounddevice as sd

from .config import Config

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
    def __init__(self, cfg: Config | None = None) -> None:
        # Defaults are fine for a throwaway probe (the onboarding microphone
        # test builds one); the real dictation recorder gets the live config.
        self.cfg = cfg if cfg is not None else Config()
        self._stream: sd.InputStream | None = None
        # _lock guards _chunks/_ring/is_recording: the PortAudio callback runs
        # on its own thread while start/stop/cancel are called from the hotkey
        # thread.
        self._lock = threading.Lock()
        # _stream_lock serialises opening and closing the stream against each
        # other and against start(). Opening is slow, and a quick hotkey tap
        # used to land stop() in the middle of that window: _stream was still
        # None, so stop closed nothing, then start finished and assigned a
        # live stream nobody would ever close. Python then collected that
        # orphan while PortAudio still held its callback pointer, and the next
        # audio block jumped into freed memory — an 0xc0000005 access
        # violation reported against "unknown"/_cffi_backend rather than any
        # traceback. Holding this across the whole operation makes a tap
        # simply wait for the open to finish and then close it properly.
        self._stream_lock = threading.RLock()
        self._chunks: list[np.ndarray] = []
        # Rolling pre-roll window, filled only while *not* recording.
        self._ring: collections.deque[np.ndarray] = collections.deque()
        self._ring_samples = 0
        self._preroll_samples = 0
        self._hold_started = 0.0
        self.level = 0.0
        self.is_recording = False
        self._stream_rate = SAMPLE_RATE
        self._open_device: int | None = None
        self._release_timer: threading.Timer | None = None
        # device -> sample rate known to work, so the 16 kHz attempt that this
        # device already rejected is not repeated on every single recording.
        self._rate_cache: dict[object, int] = {}

    # ------------------------------------------------------------- capture path

    def _preroll_budget(self) -> int:
        """Pre-roll length in samples *at the stream's own rate*."""
        return max(0, int(self.cfg.preroll_ms) * self._stream_rate // 1000)

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("audio status: %s", status)
        block = indata[:, 0].copy()
        with self._lock:
            if self.is_recording:
                self._chunks.append(block)
                rms = float(np.sqrt(np.mean(block**2))) if block.size else 0.0
                self.level = min(1.0, rms * 18)
                return
            # Idle: keep the tail end of what the microphone is hearing, so a
            # dictation started a moment late still has its first word.
            budget = self._preroll_budget()
            if budget <= 0:
                if self._ring:
                    self._ring.clear()
                    self._ring_samples = 0
                return
            self._ring.append(block)
            self._ring_samples += len(block)
            while self._ring and self._ring_samples - len(self._ring[0]) >= budget:
                self._ring_samples -= len(self._ring.popleft())

    # -------------------------------------------------------------- stream life

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
        preferring WASAPI (see _preferred_input_device). Retrying at the
        device's own native rate keeps the stream on WASAPI; the recording
        path resamples the result back to 16 kHz.

        The working rate is remembered per device, so a device already known
        to refuse 16 kHz is not re-probed on every reopen."""
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

    def ensure_stream(self, device: int | None = None) -> None:
        """Open the capture stream if it isn't already running.

        Called on the hotkey, and at startup when Config.mic_mode is "always".
        Raises if no device could be opened at all.
        """
        if device is None:
            device = self.cfg.input_device_index
        with self._stream_lock:
            self._cancel_release_timer()
            if self._stream is not None:
                if device == self._open_device:
                    return
                # The user picked a different microphone; swap to it.
                log.info("input device changed (%s -> %s), reopening",
                         self._open_device, device)
                self._close_stream()

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
                    stream, rate = self._open_stream(dev)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if i < len(candidates) - 1:
                        log.warning("input device %s failed (%s), trying next", dev, exc)
                    continue
                self._stream, self._stream_rate = stream, rate
                self._open_device = device
                with self._lock:
                    self._ring.clear()
                    self._ring_samples = 0
                log.info("microphone open (device=%s, rate=%d)", dev, rate)
                return
            raise last_exc if last_exc is not None else RuntimeError("no input device")

    def _close_stream(self) -> None:
        with self._stream_lock:
            self._cancel_release_timer()
            stream, self._stream = self._stream, None
            self._open_device = None
            with self._lock:
                self._ring.clear()
                self._ring_samples = 0
            if stream is None:
                return
            # Always close explicitly. Dropping the last reference and letting
            # the garbage collector do it is what turns a stray stream into a
            # native crash: PortAudio keeps calling the callback the collector
            # has already freed.
            try:
                stream.stop()
            finally:
                stream.close()
            log.info("microphone closed")

    def release(self) -> None:
        """Close the stream now — device change, or application shutdown."""
        self._close_stream()

    def _cancel_release_timer(self) -> None:
        if self._release_timer is not None:
            self._release_timer.cancel()
            self._release_timer = None

    def _schedule_release(self) -> None:
        """Apply Config.mic_mode once a dictation has finished."""
        mode = self.cfg.mic_mode
        if mode == "always":
            return
        if mode == "on_demand":
            self._close_stream()
            return
        with self._stream_lock:
            self._cancel_release_timer()
            delay = max(1, int(self.cfg.mic_idle_close_sec))
            self._release_timer = threading.Timer(delay, self._close_stream)
            self._release_timer.daemon = True
            self._release_timer.start()

    # ------------------------------------------------------------ recording API

    def start(self, device: int | None = None) -> None:
        """`device` overrides the user's saved microphone choice (see
        Config.input_device_index); None means "use the saved one"."""
        with self._stream_lock:
            if self.is_recording:
                return
            self.ensure_stream(device)  # raises if nothing could be opened
            with self._lock:
                # Seed the recording with the pre-roll window, so the buffer
                # already contains the moment before the key went down.
                seed = list(self._ring)
                self._ring.clear()
                self._ring_samples = 0
                self._chunks = seed
                self._preroll_samples = sum(len(b) for b in seed)
                self.level = 0.0
                self.is_recording = True
            self._hold_started = time.monotonic()
            log.info("recording started (pre-roll %d ms)",
                     self._preroll_samples * 1000 // max(1, self._stream_rate))

    def _wait_tail(self) -> None:
        """Keep capturing for Config.tail_ms after the key came up. Polls so a
        cancel arriving mid-wait (which clears is_recording) ends it at once."""
        deadline = time.monotonic() + max(0, int(self.cfg.tail_ms)) / 1000
        while self.is_recording and time.monotonic() < deadline:
            time.sleep(0.025)

    def _collect(self) -> tuple[np.ndarray, int]:
        """Stop accumulating; return (audio at stream rate, pre-roll samples)."""
        with self._lock:
            self.is_recording = False
            chunks, self._chunks = self._chunks, []
            preroll = self._preroll_samples
            self._preroll_samples = 0
            self.level = 0.0
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return audio, preroll

    def stop(self) -> np.ndarray:
        """Return captured audio, or raise EmptyRecording.

        A very quick tap blocks here until an in-flight start() has finished
        opening its stream, so the stream is closed rather than stranded.
        """
        was_recording = self.is_recording
        held = time.monotonic() - self._hold_started if was_recording else 0.0
        # A genuine hold earns the tail window; a mis-tap is going to be
        # rejected anyway, so don't make the user wait to be told so. The wait
        # deliberately happens before the lock below — it is a sleep.
        if was_recording and held >= MIN_DURATION:
            self._wait_tail()

        with self._stream_lock:
            # Taking the lock puts us strictly after any in-flight start(): a
            # tap that arrives mid-open then tears down the stream that open
            # produced, instead of leaving it stranded (see __init__).
            if not was_recording and self.is_recording:
                # start() has only just finished — this was a tap, not speech.
                held = time.monotonic() - self._hold_started
            raw, preroll = self._collect()
            self._schedule_release()
        audio = _resample(raw, self._stream_rate, SAMPLE_RATE)

        if held < MIN_DURATION:
            # Measured from the key, not from the buffer: the pre-roll makes
            # every buffer at least preroll_ms long, so buffer length can no
            # longer tell a tap from a real dictation.
            log.info("recording rejected as too short (held %.2fs)", held)
            raise EmptyRecording("short")
        peak = float(np.abs(audio).max()) if audio.size else 0.0
        if peak < MIN_PEAK:
            # Long enough to be a real attempt, but not a whisper of signal —
            # this is "the microphone isn't picking anything up", not "you let
            # go too fast". Conflating the two produced a confusing "recording
            # too short" message after a 78-second silent hold.
            log.info("recording rejected as silent (%.2fs, peak %.3f)",
                     len(audio) / SAMPLE_RATE, peak)
            raise EmptyRecording("silent")
        log.info("recording stopped (%.2fs held, %.2fs audio incl. %d ms pre-roll)",
                 held, len(audio) / SAMPLE_RATE, preroll * 1000 // max(1, self._stream_rate))
        return audio

    def cancel(self) -> None:
        # Same lock discipline as stop(): a cancel landing inside an in-flight
        # start() must run after it, or it would cancel nothing and leave a
        # live stream behind.
        with self._stream_lock:
            if not self.is_recording and self._stream is None:
                return
            self._collect()
            self._schedule_release()
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
