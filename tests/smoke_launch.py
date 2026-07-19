"""Headless launch smoke test: wire everything up the way __main__ does,
drive one dictation session through the real Dictation class via the sink
(so no other app is touched), and confirm the tray icon + hotkey listener
build and tear down cleanly. Run: uv run python tests/smoke_launch.py
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

from windictoo.app import Dictation, State
from windictoo.config import Config
from windictoo.hotkey import HotkeyListener
from windictoo.transcribe import Transcriber

PHRASE = "Проверка запуска приложения"


def synth(text: str, out: Path) -> bool:
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like "*RU*" }} | Select-Object -First 1
if ($null -eq $v) {{ Write-Output "NOVOICE"; exit 0 }}
$s.SelectVoice($v.VoiceInfo.Name)
$s.SetOutputToWaveFile("{out.as_posix()}")
$s.Speak("{text}")
$s.Dispose(); Write-Output "OK"
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True, text=True, timeout=120,
    )
    return "OK" in r.stdout and out.exists()


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if rate != 16000:
        idx = np.linspace(0, len(a) - 1, int(len(a) * 16000 / rate))
        a = np.interp(idx, np.arange(len(a)), a).astype(np.float32)
    return a


def main() -> int:
    ok = True

    # 1. Tray icon builds (image render + menu) without starting its loop.
    from windictoo.tray import Tray

    cfg = Config(model="small", compute_type="int8", language="ru", threads=4)
    dictation = Dictation(cfg)
    tray = Tray(dictation, on_show=lambda: None, on_settings=lambda: None, on_quit=lambda: None)
    assert tray.icon is not None
    tray._on_state(State.RECORDING)  # exercises icon re-render + title
    print("[OK] tray icon + menu build, state update works")

    # 1b. GUI builds (main window + settings tabs + overlay) without mainloop.
    import tkinter as tk

    from windictoo.gui import WinDictooGUI

    gui = WinDictooGUI(cfg, dictation, apply_hotkey=lambda spec: None, on_quit=lambda: None)
    gui.open_settings()
    gui.root.update()  # force widget realization
    assert gui.settings_win is not None and gui.settings_win.winfo_exists()
    gui._build_overlay()
    gui.root.update()
    gui.root.destroy()
    print("[OK] GUI main window, settings tabs and overlay build")

    # Fresh dictation for the session test (previous root was destroyed).
    dictation = Dictation(cfg)

    # 2. Hotkey listener starts and stops (registers the OS-level hook).
    fired = {"down": 0, "up": 0}
    hl = HotkeyListener(
        cfg.hotkey,
        on_press=lambda: fired.__setitem__("down", fired["down"] + 1),
        on_release=lambda: fired.__setitem__("up", fired["up"] + 1),
        on_cancel=lambda: None,
    )
    hl.start()
    time.sleep(0.3)
    hl.stop()
    print("[OK] hotkey listener start/stop (registered global hook)")

    # 3. Full session through Dictation via sink, with real transcription.
    wav = Path(__file__).with_name("_smoke.wav")
    if not synth(PHRASE, wav):
        print("[SKIP] no Russian SAPI voice; session test skipped")
        return 0 if ok else 1

    # Pre-load the model so the session isn't waiting on a download.
    Transcriber(cfg).load()  # warms HF cache path
    dictation.transcriber.load()

    result: dict[str, str] = {}
    done = threading.Event()

    def sink(text: str) -> None:
        result["text"] = text
        done.set()

    dictation.sink = sink

    # Simulate: start recording, feed synthesized audio, process.
    audio = load_wav(wav)
    dictation.start()
    assert dictation.state is State.RECORDING
    # Replace the live mic buffer with our synthesized speech.
    dictation.recorder._chunks = [audio]
    dictation.recorder._peak = 1.0
    dictation.stop_and_process()

    if not done.wait(timeout=120):
        print("[FAIL] session did not complete within 120s")
        return 1

    text = result.get("text", "")
    lowered = text.lower()
    hits = [w for w in ("проверка", "запуска", "приложения") if w in lowered]
    if len(hits) >= 2:
        print(f"[OK] full session via Dictation: {text!r}")
    else:
        print(f"[FAIL] unexpected transcript: {text!r}")
        ok = False

    wav.unlink(missing_ok=True)
    print("=== SMOKE PASSED ===" if ok else "=== SMOKE FAILED ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
