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

from windictoo import hotkey, i18n, refine, update
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


def test_audio_resample_preserves_duration_and_signal():
    from windictoo import audio

    # A 1-second 440 Hz tone captured at 48 kHz (WASAPI's typical native
    # rate on this machine) must resample to ~16000 samples at 16 kHz
    # without collapsing to silence.
    t = np.linspace(0, 1.0, 48000, endpoint=False)
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    resampled = audio._resample(tone, 48000, 16000)
    assert abs(len(resampled) - 16000) <= 1
    assert np.abs(resampled).max() > 0.5  # signal survived, not silence

    # No-op when rates already match, and empty input never raises.
    assert audio._resample(tone, 16000, 16000) is tone
    assert audio._resample(np.zeros(0, dtype=np.float32), 48000, 16000).size == 0


def test_quick_tap_never_strands_an_open_stream():
    """Reproduces the 0xc0000005 crash: stop() arriving while start() is still
    opening its (slow) stream.

    The old code set is_recording before opening, so stop() saw _stream is
    None, closed nothing, and start() then assigned a live stream nobody would
    ever close. Python collected that orphan while PortAudio still held its
    callback pointer — the next audio block jumped into freed memory.

    Here the open is deliberately slowed and stop() is fired in the middle.
    Every stream that gets opened must also get closed.

    Pinned to mic_mode="on_demand" so "closed" means "closed by the time stop()
    returns". The other modes keep the stream deliberately — that is what
    test_lazy_mode_keeps_the_stream_but_still_releases_it covers.
    """
    import threading
    import time

    from windictoo import audio

    opened, closed = [], []

    class FakeStream:
        def __init__(self, rate):
            self.rate = rate
            opened.append(self)

        def start(self):
            time.sleep(0.25)  # a real slow open (probe + retry)

        def stop(self):
            pass

        def close(self):
            closed.append(self)

    rec = audio.Recorder(Config(mic_mode="on_demand"))
    rec._make_stream = lambda device, rate: (lambda s: (s.start(), s)[1])(FakeStream(rate))

    threading.Thread(target=lambda: rec.start(device=None), daemon=True).start()
    time.sleep(0.05)  # land squarely inside the open
    with pytest.raises(audio.EmptyRecording):
        rec.stop()

    assert opened, "the test must actually open a stream to be meaningful"
    assert len(closed) == len(opened), (
        f"stranded stream: opened {len(opened)}, closed {len(closed)}"
    )
    assert rec._stream is None
    assert rec.is_recording is False


def test_failed_open_does_not_wedge_the_recorder():
    """A device that fails to open must leave is_recording False. It used to
    stay True, so every later start() returned at the guard and dictation was
    dead until the app restarted."""
    from windictoo import audio

    rec = audio.Recorder()

    def always_fails(device, rate):
        raise RuntimeError("no such device")

    rec._make_stream = always_fails
    with pytest.raises(Exception):
        rec.start(device=None)
    assert rec.is_recording is False, "a failed open must not wedge the recorder"
    assert rec._stream is None


def test_sample_rate_is_cached_per_device():
    """A device that rejects 16 kHz must be probed once, not on every
    recording — that probe cost hundreds of ms and widened the race window."""
    from windictoo import audio

    rec = audio.Recorder()
    attempts = []

    class FakeStream:
        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    def picky(device, rate):
        attempts.append(rate)
        if rate == audio.SAMPLE_RATE:
            raise RuntimeError("Invalid sample rate")
        return FakeStream()

    rec._make_stream = picky
    rec._rate_cache[7] = 48000  # already learned
    stream, rate = rec._open_stream(7)
    assert rate == 48000
    assert attempts == [48000], f"cached rate should be used directly, got {attempts}"


def test_split_uninstall_command():
    from windictoo import oldversions

    assert oldversions._split_uninstall_command(
        r'"C:\Users\me\AppData\Local\Programs\VoxWin\unins000.exe"'
    ) == [r"C:\Users\me\AppData\Local\Programs\VoxWin\unins000.exe"]
    assert oldversions._split_uninstall_command(
        r'"C:\Program Files\App\unins000.exe" /SILENT'
    ) == [r"C:\Program Files\App\unins000.exe", "/SILENT"]


def test_find_old_installs_never_raises():
    from windictoo import oldversions

    # This machine has no VoxWin/WnDic leftovers right now, but the real
    # point is that a missing registry key must return [], never raise.
    assert oldversions.find_old_installs() == []


def test_purge_stale_autostart_entries_never_raises():
    from windictoo import oldversions

    # No leftover Run-key values under old names on this machine either —
    # the point is a missing value must be swallowed, never raise.
    oldversions.purge_stale_autostart_entries()


def test_remove_legacy_startup_shortcut_never_raises():
    from windictoo import autostart

    # No leftover Startup-folder shortcut on this machine — must be a no-op,
    # never raise.
    autostart.remove_legacy_startup_shortcut()


def test_update_is_newer():
    assert update.is_newer("1.4.0", "1.3.0") is True
    assert update.is_newer("v1.4.0", "1.3.0") is True  # tolerate a "v" prefix
    assert update.is_newer("1.3.0", "1.3.0") is False
    assert update.is_newer("1.2.9", "1.3.0") is False
    assert update.is_newer("1.3.0", "1.3") is True  # missing patch counts as .0
    assert update.is_newer("garbage", "1.3.0") is False  # never crash on a bad tag


def test_update_prefers_setup_installer_asset():
    setup = {"name": "WinDictoo-Setup-1.7.3.exe"}
    portable = {"name": "WinDictoo-1.7.3-portable.exe"}
    zip_ = {"name": "WinDictoo-1.7.3-win64.zip"}
    # The installer wins regardless of asset order in the release.
    assert update._pick_asset([zip_, portable, setup]) is setup
    # Without an installer any exe will do; a zip alone is not runnable.
    assert update._pick_asset([zip_, portable]) is portable
    assert update._pick_asset([zip_]) is None


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


def test_detect_system_language_is_always_supported():
    from windictoo.config import _SUPPORTED_LANGS, _detect_system_language

    # Whatever this machine's locale resolves to, it must be one of the
    # codes the language picker actually offers — never raise, never return
    # something gui.LANGS has no entry for.
    assert _detect_system_language() in _SUPPORTED_LANGS


def test_config_language_default_factory_is_overridable():
    # A brand-new Config() gets the detected system language, but an
    # existing saved value (what Config.load() passes explicitly) must
    # always win — this is the whole point of using default_factory here.
    assert Config(language="ru").language == "ru"
    assert Config().language in {"en", "ru", "de", "fr", "es", "zh", "tr", "hy"}


def test_config_ui_language_is_independent_of_language():
    # The interface language and the speech-recognition language are
    # deliberately separate settings — changing one must never move the other.
    cfg = Config(language="ru", ui_language="en")
    assert cfg.language == "ru"
    assert cfg.ui_language == "en"
    assert Config().ui_language in {"en", "ru", "de", "fr", "es", "zh", "tr", "hy"}


def test_every_palette_is_readable():
    """Guards the palette-level half of the contrast problem: a label placed
    on ACCENT must clear WCAG AA-large in *every* theme. choc-gold shipped
    with white-on-gold at 2.85:1 and geek-black had text at 1.06:1 on its
    neon accent — both unreadable, both invisible to a test that only looked
    at one theme."""
    from windictoo import theme

    bad = []
    for key, pal in theme.PALETTES.items():
        checks = [
            ("ON_ACCENT on ACCENT", pal["ON_ACCENT"], pal["ACCENT"]),
            ("TEXT on BG", pal["TEXT"], pal["BG"]),
            ("TEXT on CARD", pal["TEXT"], pal["CARD"]),
            ("TEXT on CARD_HI", pal["TEXT"], pal["CARD_HI"]),
            ("MUTED on CARD", pal["MUTED"], pal["CARD"]),
        ]
        for label, fg, bg in checks:
            ratio = theme.contrast_ratio(fg, bg)
            if ratio < theme.AA_LARGE:
                bad.append(f"{key}: {label} = {ratio:.2f}:1 ({fg} on {bg})")
    assert not bad, "unreadable colour pairs:\n  " + "\n  ".join(bad)


def test_readable_on_prefers_brand_colour_then_falls_back():
    from windictoo import theme

    # Keeps the on-brand choice when it is legible...
    assert theme.readable_on("#000000", "#39ff14", "#ffffff") == "#39ff14"
    # ...and refuses it when it is not, falling through to the safe option.
    assert theme.readable_on("#39ff14", "#3aff15", "#000000") == "#000000"
    # Never returns nothing, even when handed junk.
    assert theme.readable_on("#ffffff", "not-a-colour").startswith("#")


def test_i18n_every_key_covers_all_eight_languages():
    from windictoo import i18n

    incomplete = {k: sorted(set(i18n.SUPPORTED) - v.keys()) for k, v in i18n.STRINGS.items()
                  if set(v.keys()) != set(i18n.SUPPORTED)}
    assert incomplete == {}, f"keys missing translations: {incomplete}"


def test_i18n_t_formats_and_falls_back():
    from windictoo import i18n

    i18n.set_language("de")
    assert i18n.t("common.later") == "Später"
    assert i18n.t("common.error_with", error="boom") == "Fehler: boom"
    assert i18n.t("no.such.key") == "no.such.key"  # never raises, never blank
    i18n.set_language("ru")  # restore default for any test relying on it


def test_i18n_state_and_tray_labels_cover_every_state():
    from windictoo import i18n
    from windictoo.app import State

    for state in State:
        assert i18n.state_label(state) != f"state.{state}"  # resolved, not a raw key
        assert i18n.tray_label(state) != f"tray.{state}"


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


@pytest.fixture(scope="module")
def typing_sandbox():
    """A focused window that receives test keystrokes.

    type_unicode() drives the real SendInput API, so it types into whatever
    window currently has focus. Without this sandbox a plain `pytest` run
    dumps the sample text straight into whatever the developer happened to
    have open — a document, a chat, an editor. Owning the focused window
    contains it, and lets us assert the text actually arrived instead of
    only that the call returned True.

    Module-scoped on purpose: Tk cannot reliably re-initialise after a root
    is destroyed inside the same process (the second Tk() fails with
    "Can't find a usable init.tcl"), so every typing test shares one root.
    """
    import tkinter as tk

    root = tk.Tk()
    root.title("windictoo typing sandbox")
    root.geometry("420x90+60+60")
    entry = tk.Entry(root, width=64)
    entry.pack(fill="both", expand=True, padx=8, pady=8)
    root.update()
    root.lift()
    root.focus_force()
    entry.focus_force()
    root.update()
    try:
        yield root, entry
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def _own_the_foreground(root, entry, attempts: int = 20) -> bool:
    """Take real OS foreground focus, and confirm Windows agrees.

    SendInput delivers to whatever window is foreground *at that moment*.
    If the grab fails we must not type at all, or the sample text lands in
    the developer's editor/chat instead — so callers skip rather than fire
    blindly. Windows also refuses focus changes from background processes,
    hence the retry loop."""
    import ctypes
    import time

    user32 = ctypes.windll.user32
    for _ in range(attempts):
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            entry.focus_force()
            root.update()
        except Exception:  # noqa: BLE001
            return False
        our_hwnd = user32.GetAncestor(entry.winfo_id(), 2) or root.winfo_id()
        if user32.GetForegroundWindow() == our_hwnd:
            return True
        time.sleep(0.05)
    return False


def _type_and_read(root, entry, text: str, timeout: float = 3.0) -> str:
    """Send `text` into our own focused Entry and read back what arrived."""
    import time

    import pytest as _pytest

    from windictoo import insert

    if not _own_the_foreground(root, entry):
        _pytest.skip("could not take foreground focus — refusing to type into another window")

    entry.delete(0, "end")
    root.update()
    assert insert.type_unicode(text) is True, f"SendInput rejected {text!r}"

    expected = len(text)
    deadline = time.time() + timeout
    while time.time() < deadline:
        root.update()
        if len(entry.get()) >= expected:
            break
        time.sleep(0.02)
    root.update()
    return entry.get()


# A Tk Entry decodes incoming characters through the system ANSI codepage
# rather than Unicode, so "Grüße" arrives as "GrьЯe" on a Russian-locale
# Windows. That is a Tk limitation, not a defect in type_unicode (which
# encodes UTF-16 and sets KEYEVENTF_UNICODE correctly — real editors and
# browsers receive it intact). Tests therefore assert on ASCII exactly and
# on *character count* for everything else: a dropped or duplicated
# keystroke still fails, without the result depending on the machine locale.


def test_type_unicode_delivers_text_to_focused_field(typing_sandbox):
    """Real SendInput into a real focused control — the union layout,
    key-event flags and UTF-16 encoding all have to be right for anything to
    arrive at all (an undersized union once made every keystroke vanish)."""
    from windictoo import insert

    root, entry = typing_sandbox
    assert _type_and_read(root, entry, "hello world") == "hello world"
    assert len(_type_and_read(root, entry, "Привет")) == len("Привет")
    assert len(_type_and_read(root, entry, "Grüße")) == len("Grüße")

    # The surrogate-pair path still gets exercised, but Tk 8.6 cannot store
    # astral-plane characters at all, so only the call is asserted here.
    assert insert.type_unicode("😀") is True
    assert insert.type_unicode("") is True


def test_type_unicode_paces_long_text(typing_sandbox):
    """Above _PACE_THRESHOLD_CHARS (80), type_unicode batches SendInput calls
    instead of one giant burst (some legacy Win32 controls drop keystrokes
    otherwise) — every character must still arrive."""
    from windictoo import insert

    long_text = " ".join(i18n.GREETINGS) * 2
    assert len(long_text) > insert._PACE_THRESHOLD_CHARS, "sample must exercise the batching path"
    root, entry = typing_sandbox
    assert len(_type_and_read(root, entry, long_text)) == len(long_text)


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


# --------------------------------------------------- persistent mic / pre-roll


class _DummyStream:
    """Stands in for sd.InputStream: the tests drive _callback themselves."""

    def __init__(self, closed: list | None = None) -> None:
        self._closed = closed

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        if self._closed is not None:
            self._closed.append(self)


def _recorder(cfg, closed: list | None = None):
    from windictoo import audio

    rec = audio.Recorder(cfg)
    rec._make_stream = lambda device, rate: _DummyStream(closed)
    rec.ensure_stream(None)
    return rec


def _feed(rec, seconds: float, value: float = 0.5) -> None:
    """Push `seconds` of constant-amplitude audio through the callback."""
    n = int(seconds * 16000)
    rec._callback(np.full((n, 1), value, dtype=np.float32), n, None, None)


def test_preroll_captures_audio_from_before_the_hotkey():
    """The whole point of the persistent stream: what was said in the moment
    before the key went down is already in the buffer."""
    import time

    rec = _recorder(Config(mic_mode="on_demand", preroll_ms=400, tail_ms=0))
    _feed(rec, 0.4)  # spoken just before the user pressed the hotkey
    rec.start()
    time.sleep(0.4)  # clear MIN_DURATION, which is measured from the key
    _feed(rec, 1.0)

    out = rec.stop()
    assert len(out) / 16000 == pytest.approx(1.4, abs=0.05), (
        "pre-roll audio was dropped instead of prepended"
    )


def test_a_tap_is_still_too_short_even_with_a_full_preroll():
    """Regression guard for the pre-roll change: 'too short' used to be read
    off the buffer length, which the pre-roll now inflates to 400 ms on its
    own. It has to come from how long the key was actually held."""
    from windictoo import audio

    rec = _recorder(Config(mic_mode="on_demand", preroll_ms=400, tail_ms=0))
    _feed(rec, 0.4)  # a full ring, so the buffer alone looks like real speech
    rec.start()

    with pytest.raises(audio.EmptyRecording) as exc:
        rec.stop()
    assert exc.value.reason == "short"


def test_preroll_ring_stays_bounded():
    """It runs for as long as the app does; it must not grow."""
    rec = _recorder(Config(preroll_ms=400))
    for _ in range(50):  # five seconds through a 0.4 s window
        _feed(rec, 0.1)

    budget = 400 * 16000 // 1000
    assert rec._ring_samples >= budget, "the window is not being kept full"
    assert rec._ring_samples < budget + 2 * 1024, "the ring buffer is growing"
    assert rec._ring_samples == sum(len(b) for b in rec._ring), "sample count drifted"


def test_lazy_mode_keeps_the_stream_but_still_releases_it():
    import time

    closed: list = []
    rec = _recorder(Config(mic_mode="lazy", mic_idle_close_sec=30, tail_ms=0), closed)
    _feed(rec, 0.1)
    rec.start()
    time.sleep(0.4)
    _feed(rec, 0.5)
    rec.stop()

    assert rec._stream is not None, "lazy mode must keep the device warm"
    assert not closed
    rec.release()
    assert rec._stream is None and closed, "release() must close the device"
    assert rec._release_timer is None, "the pending close timer must be cancelled"


# ------------------------------------------------ refinement: privacy & reasoning


def test_cloud_models_are_recognised():
    assert refine.is_cloud_model("glm-5.2:cloud")
    assert refine.is_cloud_model("  GPT-OSS:Cloud  ")
    assert not refine.is_cloud_model("qwen2.5:3b")
    assert not refine.is_cloud_model("cloudy-model:latest")


def test_cloud_model_is_refused_without_sending_anything(monkeypatch):
    """The loopback check cannot catch this: Ollama accepts a ':cloud' model
    on 127.0.0.1 and forwards it to its own servers. So the transcript must
    never reach the socket in the first place."""
    def explode(*a, **k):
        raise AssertionError("a request was made for a cloud model")

    monkeypatch.setattr(refine.httpx, "Client", explode)

    out, fell_back = refine.refine(
        "секретный текст", "http://127.0.0.1:11434", "glm-5.2:cloud", 20.0
    )
    assert out == "секретный текст" and fell_back is True


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise refine.httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=None
            )

    def json(self):
        return self._payload


def _fake_ollama(monkeypatch, responses):
    """Swap httpx.Client for one serving `responses`; returns the sent payloads."""
    sent: list[dict] = []
    queue = list(responses)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            sent.append(json)
            return queue.pop(0)

    monkeypatch.setattr(refine.httpx, "Client", lambda **kw: _FakeClient())
    return sent


def test_reasoning_is_switched_off_in_the_request(monkeypatch):
    """Measured against qwen3.6: with reasoning left on, the model spent all
    256 tokens narrating and returned an empty answer; with think=false it
    answered correctly in 12."""
    sent = _fake_ollama(monkeypatch, [
        _FakeResponse({"message": {"content": "Привет, как дела?"}}),
    ])

    out, fell = refine.refine("привет как дела", "http://127.0.0.1:11434", "qwen3:8b", 20.0)
    assert fell is False and out == "Привет, как дела?"
    assert sent[0]["think"] is False, "reasoning must be requested off"


def test_older_server_rejecting_think_is_retried_plainly(monkeypatch):
    """Not every Ollama build knows the key; refinement must not be lost to it."""
    sent = _fake_ollama(monkeypatch, [
        _FakeResponse({"error": "unknown field"}, status=400),
        _FakeResponse({"message": {"content": "Привет, как дела?"}}),
    ])

    out, fell = refine.refine("привет как дела", "http://127.0.0.1:11434", "old:1b", 20.0)
    assert fell is False and out == "Привет, как дела?"
    assert sent[0]["think"] is False and "think" not in sent[1]


def test_reasoning_only_reply_falls_back(monkeypatch):
    """The exact qwen3.6 failure: everything in "thinking", nothing in
    "content". Must fall back to the transcript, not paste an empty string."""
    _fake_ollama(monkeypatch, [
        _FakeResponse({"message": {"content": "", "thinking": "Let me consider…"}}),
    ])

    out, fell = refine.refine("привет как дела", "http://127.0.0.1:11434", "qwen3:8b", 20.0)
    assert fell is True and out == "привет как дела"


def test_reasoning_narration_is_stripped():
    assert refine.strip_reasoning("<think>Hmm, what do they mean?</think>Привет, мир.") \
        == "Привет, мир."
    assert refine.strip_reasoning("<THINKING>a</THINKING> Text") == "Text"
    # Ran out of tokens mid-thought: no answer ever arrived, so nothing is
    # usable — better empty (which validate() rejects) than narration pasted
    # into the user's document.
    assert refine.strip_reasoning("<think>still thinking and thinking") == ""
    assert refine.strip_reasoning("Чи​стый‍ текст") == "Чистый текст"


def test_reasoning_model_reply_survives_validation():
    """Regression for the whole point of stripping: a long <think> block used
    to push the reply past validate()'s length guard, so refinement silently
    fell back on exactly the models people install first (qwen3, deepseek-r1)."""
    original = "привет как дела"
    reply = ("<think>" + "The user dictated a greeting. " * 30 + "</think>"
             + "Привет, как дела?")
    assert refine.validate(original, reply)[0] is False, "test premise: raw reply is rejected"
    assert refine.validate(original, refine.strip_reasoning(reply))[0] is True


# ------------------------------------------------------- insertion status text


def test_successful_typing_does_not_claim_the_text_is_in_the_clipboard(monkeypatch):
    """Typing is the default insertion path and never touches the clipboard,
    yet every successful dictation used to end with "the text is in the
    clipboard, paste it with Ctrl+V"."""
    from windictoo import app as app_mod
    from windictoo import insert as insert_mod

    d = app_mod.Dictation(Config(refine_enabled=False))
    monkeypatch.setattr(d.transcriber, "transcribe", lambda audio: ("Привет.", "ru"))
    monkeypatch.setattr(insert_mod, "insert", lambda *a, **k: "typed")

    d._pipeline(np.zeros(16000, dtype=np.float32))
    assert d.state is app_mod.State.DONE
    assert d.message == "", f"claimed something about the clipboard: {d.message!r}"


def test_clipboard_only_still_tells_the_user_to_paste(monkeypatch):
    """The hint is right in the one case it was written for: the text reached
    the clipboard but the synthetic Ctrl+V did not land."""
    from windictoo import app as app_mod
    from windictoo import insert as insert_mod

    d = app_mod.Dictation(Config(refine_enabled=False))
    monkeypatch.setattr(d.transcriber, "transcribe", lambda audio: ("Привет.", "ru"))
    monkeypatch.setattr(insert_mod, "insert", lambda *a, **k: "clipboard_only")

    d._pipeline(np.zeros(16000, dtype=np.float32))
    assert d.state is app_mod.State.DONE
    assert d.message == i18n.t("app.clipboard_paste_hint")


# ------------------------------------------------------------ engine catalogue


def test_unknown_model_id_falls_back_instead_of_raising():
    """config.json is documented as hand-editable, and a config written by a
    newer build must not brick dictation."""
    from windictoo import engine

    assert engine.spec("no-such-model").id == engine.DEFAULT_MODEL


def test_onnx_models_declare_that_they_ignore_the_language_setting():
    from windictoo import engine

    gigaam = engine.spec("gigaam-v3-ru")
    assert gigaam.honors_language is False
    assert gigaam.fixed_language == "ru"
    assert engine.spec("parakeet-v3").honors_language is False
    assert engine.spec("small").honors_language is True
    assert engine.spec("small").fixed_language is None


def test_model_catalogue_filters_by_language():
    from windictoo import engine

    armenian = {m.id for m in engine.models_for("hy")}
    assert "small" in armenian, "Whisper covers every language the app offers"
    assert "gigaam-v3-ru" not in armenian and "parakeet-v3" not in armenian

    german = {m.id for m in engine.models_for("de")}
    assert "parakeet-v3" in german and "gigaam-v3-ru" not in german
    assert "gigaam-v3-ru" in {m.id for m in engine.models_for("ru")}
