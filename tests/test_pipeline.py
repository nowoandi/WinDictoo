"""End-to-end and unit checks.

The integration test synthesises speech with Windows SAPI and runs it through
the real Whisper model, so the transcription path is exercised for real rather
than mocked. It is skipped (never silently passed) when SAPI has no voice for
the language.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from windictoo import hotkey, refine, update
from windictoo.config import Config
from windictoo.transcribe import Transcriber, normalize_whitespace, strip_artifacts


# --- pure logic -------------------------------------------------------------


def test_strip_artifacts_removes_annotations():
    assert strip_artifacts("привет [музыка] мир").strip() == "привет   мир".strip()
    assert "(so to speak)" in strip_artifacts("keep (so to speak) this")
    assert strip_artifacts("hi (applause) there").count("applause") == 0


def test_normalize_whitespace():
    assert normalize_whitespace("  a   b \n\n  c  ") == "a b\nc"


def test_hotkey_parse():
    mods, main = hotkey.parse(["ctrl", "alt", "space"])
    assert mods == ["ctrl", "alt"]
    assert hotkey.describe(["ctrl", "alt", "space"]) == "Ctrl + Alt + Space"


def test_hotkey_rejects_modifier_only():
    with pytest.raises(ValueError):
        hotkey.parse(["ctrl", "alt"])


def test_token_to_vk():
    assert hotkey.token_to_vk("space") == 0x20
    assert hotkey.token_to_vk("f9") == 0x78
    assert hotkey.token_to_vk("a") == 0x41
    assert hotkey.token_to_vk("1") == 0x31
    assert hotkey.token_to_vk("weird") is None


def _feed_hotkey(hk, events_msg_vk):
    """Drive the win32 filter with synthetic (msg, vk) events; return which
    events were suppressed."""
    suppressed = []

    class _FakeListener:
        def suppress_event(self):
            suppressed.append(True)
            raise RuntimeError("SUPPRESS")  # mirrors pynput raising to signal

    hk._listener = _FakeListener()
    hk._fire = lambda fn: fn()  # run callbacks synchronously for the test

    class _Data:
        def __init__(self, vk):
            self.vkCode = vk

    for msg, vk in events_msg_vk:
        try:
            hk._win32_filter(msg, _Data(vk))
        except RuntimeError:
            pass
    return suppressed


def test_hotkey_suppresses_main_key_and_fires_once():
    """Ctrl+Alt+Space: Space is swallowed (incl. auto-repeat); press/release
    fire exactly once."""
    fired = []
    hk = hotkey.HotkeyListener(
        ["ctrl", "alt", "space"],
        on_press=lambda: fired.append("down"),
        on_release=lambda: fired.append("up"),
        on_cancel=lambda: fired.append("cancel"),
        suppress=True,
    )
    kd, ku = 0x0100, 0x0101
    suppressed = _feed_hotkey(hk, [
        (kd, 0x11),  # Ctrl down
        (kd, 0x12),  # Alt down
        (kd, 0x20),  # Space down -> fire "down", suppress
        (kd, 0x20),  # Space auto-repeat -> suppress, no fire
        (kd, 0x20),  # Space auto-repeat -> suppress, no fire
        (ku, 0x20),  # Space up -> fire "up", suppress
        (ku, 0x12),  # Alt up
        (ku, 0x11),  # Ctrl up
    ])
    assert fired == ["down", "up"]
    assert len(suppressed) == 4  # 3 downs + 1 up


def test_hotkey_does_not_suppress_plain_space():
    """Without the modifiers, Space is a normal key: never suppressed/fired."""
    fired = []
    hk = hotkey.HotkeyListener(
        ["ctrl", "alt", "space"],
        on_press=lambda: fired.append("down"),
        on_release=lambda: fired.append("up"),
        on_cancel=lambda: fired.append("cancel"),
        suppress=True,
    )
    kd, ku = 0x0100, 0x0101
    suppressed = _feed_hotkey(hk, [(kd, 0x20), (ku, 0x20)])  # bare Space
    assert fired == []
    assert suppressed == []


def test_refine_rejects_non_loopback():
    with pytest.raises(refine.NonLocalEndpoint):
        refine.check_loopback("http://evil.example.com:11434")
    refine.check_loopback("http://127.0.0.1:11434")
    refine.check_loopback("http://localhost:11434")


def test_refine_falls_back_when_server_absent():
    # Nothing is listening on this port; must return the raw text, not raise.
    text, fell_back = refine.refine("привет мир", "http://127.0.0.1:59999", "x", 1.0)
    assert text == "привет мир"
    assert fell_back is True


def test_refine_validate_rejects_meta_response():
    ok, _ = refine.validate("привет мир", "Вот исправленный текст: Привет, мир!")
    assert ok is False
    ok, _ = refine.validate("привет мир", "Привет, мир!")
    assert ok is True


def test_refine_validate_rejects_bloat():
    ok, reason = refine.validate("да", "да " + "и ещё много выдуманного текста " * 20)
    assert ok is False
    assert "longer" in reason


def test_update_is_newer():
    assert update.is_newer("1.4.0", "1.3.0") is True
    assert update.is_newer("v1.4.0", "1.3.0") is True  # tolerate a "v" prefix
    assert update.is_newer("1.3.0", "1.3.0") is False
    assert update.is_newer("1.2.9", "1.3.0") is False
    assert update.is_newer("1.3.0", "1.3") is True  # missing patch counts as .0
    assert update.is_newer("garbage", "1.3.0") is False  # never crash on a bad tag


def test_update_check_never_raises_when_offline():
    # Port 1 is not a routable API endpoint; this must fail closed (None),
    # not raise — an update check must never be able to break startup.
    from windictoo import update as update_module

    original = update_module._API_URL
    update_module._API_URL = "http://127.0.0.1:1/releases/latest"
    try:
        assert update.check_for_update("1.0.0") is None
    finally:
        update_module._API_URL = original


# --- integration ------------------------------------------------------------

PHRASE_RU = "Это проверка распознавания речи"


def _synthesize(text: str, out: Path, voice_hint: str = "RU") -> bool:
    """Speak `text` to a WAV via SAPI. False when no matching voice exists."""
    ps = f"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like "*{voice_hint}*" }} | Select-Object -First 1
if ($null -eq $v) {{ Write-Output "NOVOICE"; exit 0 }}
$s.SelectVoice($v.VoiceInfo.Name)
$s.SetOutputToWaveFile("{out.as_posix()}")
$s.Speak("{text}")
$s.Dispose()
Write-Output "OK"
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return "OK" in r.stdout and out.exists()


def _load_wav_16k_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        channels = w.getnchannels()
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:  # linear resample is good enough for a smoke test
        idx = np.linspace(0, len(audio) - 1, int(len(audio) * 16000 / rate))
        audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def test_sendinput_struct_size():
    """The INPUT union must be 40 bytes on x64, else SendInput rejects it.

    (Regression guard: an undersized union made SendInput fail with error 87,
    so the "type" insertion never worked. The live end-to-end proof that text
    lands in a focused field lives in tests/smoke_type.py.)
    """
    import ctypes

    from windictoo import insert

    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(insert._INPUT) == expected


def test_type_unicode_accepted_by_os():
    """SendInput accepts our well-formed events (RU, DE, surrogate pairs)."""
    from windictoo import insert

    assert insert.type_unicode("Привет") is True
    assert insert.type_unicode("Grüße") is True
    assert insert.type_unicode("emoji 😀") is True  # surrogate-pair path
    assert insert.type_unicode("") is True


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "win32", reason="SAPI is Windows-only")
def test_transcribes_synthesized_russian_speech(tmp_path):
    wav = tmp_path / "speech.wav"
    if not _synthesize(PHRASE_RU, wav):
        pytest.skip("SKIPPED: no Russian SAPI voice installed on this machine")

    audio = _load_wav_16k_mono(wav)
    assert len(audio) / 16000 > 0.5, "synthesized audio too short"

    cfg = Config(model="small", compute_type="int8", language="ru", threads=4)
    text, lang = Transcriber(cfg).transcribe(audio)

    assert text, "transcript is empty"
    lowered = text.lower()
    hits = [w for w in ("проверка", "распознавания", "речи") if w in lowered]
    assert len(hits) >= 2, f"expected keywords, got: {text!r}"
