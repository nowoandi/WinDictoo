"""Dictation session orchestration."""

from __future__ import annotations

import enum
import logging
import threading
from collections.abc import Callable

from . import insert, refine
from .audio import EmptyRecording, Recorder
from .config import Config
from .transcribe import Transcriber

log = logging.getLogger(__name__)


class State(enum.StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    REFINING = "refining"
    INSERTING = "inserting"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class Dictation:
    """One session at a time; every entry point checks the state first."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.recorder = Recorder()
        self.transcriber = Transcriber(cfg)
        self.state = State.IDLE
        self.message = ""
        # When set, the result goes here instead of into the focused app.
        self.sink: Callable[[str], None] | None = None
        self.on_state_change: Callable[[State], None] | None = None
        # Returns True if the given HWND belongs to WinDictoo itself, so we never
        # capture our own window as the insertion target.
        self.is_own_window: Callable[[int], bool] | None = None
        self._target_hwnd = 0
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    def _set_state(self, state: State, message: str = "") -> None:
        self.state = state
        self.message = message
        log.debug("state -> %s %s", state, message)
        if self.on_state_change:
            try:
                self.on_state_change(state)
            except Exception:  # noqa: BLE001
                log.exception("state change handler failed")

    def start(self) -> None:
        with self._lock:
            if self.state is not State.IDLE:
                return
            self._cancelled.clear()
            # Remember the field the user is in *now*, before anything can
            # steal focus, so the text lands there after transcription.
            hwnd = insert.foreground_window()
            if self.is_own_window is not None and self.is_own_window(hwnd):
                hwnd = 0  # don't target our own window
            self._target_hwnd = hwnd
            self._set_state(State.RECORDING)
        try:
            self.recorder.start(device=self.cfg.input_device_index)
        except Exception as exc:  # noqa: BLE001
            log.exception("could not start recording")
            self._set_state(State.ERROR, f"Микрофон недоступен: {exc}")
            self._reset_later()

    def stop_and_process(self) -> None:
        with self._lock:
            if self.state is not State.RECORDING:
                return
            self._set_state(State.TRANSCRIBING)
        try:
            audio = self.recorder.stop()
        except EmptyRecording:
            self._set_state(State.ERROR, "Запись пуста или слишком короткая")
            self._reset_later()
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("could not stop recording")
            self._set_state(State.ERROR, str(exc))
            self._reset_later()
            return
        threading.Thread(target=self._pipeline, args=(audio,), daemon=True).start()

    def _pipeline(self, audio) -> None:
        try:
            text, lang = self.transcriber.transcribe(audio)
            if self._cancelled.is_set():
                return
            if not text:
                self._set_state(State.ERROR, "Речь не распознана")
                self._reset_later()
                return

            if self.cfg.refine_enabled and self.cfg.ollama_model:
                self._set_state(State.REFINING)
                text, fell_back = refine.refine(
                    text,
                    self.cfg.ollama_endpoint,
                    self.cfg.ollama_model,
                    self.cfg.refine_timeout,
                )
                if self._cancelled.is_set():
                    return
                if fell_back:
                    self.message = "Улучшение недоступно — вставлен исходный текст"

            # A cancelled session must produce no side effects at all.
            if self._cancelled.is_set():
                return

            if self.sink is not None:
                self.sink(text)
                self._set_state(State.DONE)
                self._reset_later()
                return

            self._set_state(State.INSERTING)
            status = insert.insert(
                text,
                self.cfg.restore_clipboard,
                self._target_hwnd,
                self.cfg.insertion_method,
            )
            if status == "pasted":
                self._set_state(State.DONE)
            else:
                self._set_state(State.DONE, "Текст в буфере обмена — вставьте через Ctrl+V")
            self._reset_later()
        except Exception as exc:  # noqa: BLE001
            log.exception("pipeline failed")
            self._set_state(State.ERROR, str(exc))
            self._reset_later()

    def cancel(self) -> None:
        if self.state in (State.IDLE, State.DONE, State.CANCELLED, State.ERROR):
            return
        self._cancelled.set()
        self.recorder.cancel()
        self._set_state(State.CANCELLED)
        self._reset_later()
        log.info("cancelled by user")

    def _reset_later(self, delay: float = 1.5) -> None:
        def reset() -> None:
            if self.state in (State.DONE, State.CANCELLED, State.ERROR):
                self._set_state(State.IDLE)

        threading.Timer(delay, reset).start()

    # Hotkey entry points -------------------------------------------------

    def on_hotkey_down(self) -> None:
        if self.cfg.mode == "hold":
            self.start()
        elif self.state is State.IDLE:
            self.start()
        elif self.state is State.RECORDING:
            self.stop_and_process()

    def on_hotkey_up(self) -> None:
        if self.cfg.mode == "hold" and self.state is State.RECORDING:
            self.stop_and_process()
