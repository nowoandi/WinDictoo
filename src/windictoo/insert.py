"""Text insertion: clipboard + synthetic Ctrl+V, with clipboard restore.

Windows has no cross-app equivalent of the macOS Accessibility "set selected
text" call that works everywhere, so simulated paste is the primary path.
The previous clipboard contents are restored afterwards unless another app
wrote to the clipboard in the meantime (checked via the system sequence
number, so we never clobber someone else's copy).
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_VK_MENU = 0x12  # ALT
_KEYEVENTF_KEYUP = 0x0002


def foreground_window() -> int:
    """Handle of the window that currently has focus (0 if none)."""
    return int(user32.GetForegroundWindow() or 0)


def window_pid(hwnd: int) -> int:
    """Process id owning `hwnd` (0 if unknown)."""
    if not hwnd:
        return 0
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def focus_window(hwnd: int) -> bool:
    """Bring `hwnd` to the foreground, working around the focus-steal lock.

    Windows normally refuses SetForegroundWindow from a background process.
    Tapping ALT and briefly attaching to the target's input thread satisfies
    the foreground-lock timeout, which is the standard workaround.
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.GetForegroundWindow() == hwnd:
        return True
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    cur_thread = kernel32.GetCurrentThreadId()
    user32.keybd_event(_VK_MENU, 0, 0, 0)
    user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    attached = user32.AttachThreadInput(cur_thread, target_thread, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_thread, target_thread, False)
    return user32.GetForegroundWindow() == hwnd


class _Clipboard:
    """Context manager; retries because another app may hold the clipboard."""

    def __enter__(self):
        for _ in range(10):
            if user32.OpenClipboard(None):
                return self
            time.sleep(0.02)
        raise OSError("could not open clipboard")

    def __exit__(self, *exc) -> None:
        user32.CloseClipboard()


def get_text() -> str | None:
    try:
        with _Clipboard():
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.c_wchar_p(ptr).value
            finally:
                kernel32.GlobalUnlock(handle)
    except OSError:
        return None


def set_text(text: str) -> bool:
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    try:
        with _Clipboard():
            user32.EmptyClipboard()
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return False
            ptr = kernel32.GlobalLock(handle)
            ctypes.memmove(ptr, data, size)
            kernel32.GlobalUnlock(handle)
            # Ownership passes to the clipboard; do not free the handle.
            return bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
    except OSError:
        return False


def sequence_number() -> int:
    return int(user32.GetClipboardSequenceNumber())


def _send_ctrl_v() -> None:
    from pynput.keyboard import Controller, Key

    kb = Controller()
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")


# --- direct Unicode typing via SendInput -------------------------------------

_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004


_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    # The INPUT union must be as large as its biggest member (MOUSEINPUT),
    # otherwise sizeof(INPUT) is wrong and SendInput rejects with error 87.
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


# Above this many characters, type_unicode() paces itself in batches: some
# legacy Win32 edit controls drop keystrokes when a very long SendInput burst
# arrives all at once. Short dictations (the vast majority) stay a single
# burst, so normal typing speed is unaffected.
_PACE_THRESHOLD_CHARS = 80
_BATCH_CHARS = 40
_BATCH_PAUSE_SEC = 0.003


def type_unicode(text: str) -> bool:
    """Type `text` into the focused control as Unicode key events.

    This inserts at the caret of whatever currently has keyboard focus,
    without touching the clipboard. Works for BMP and surrogate-pair
    characters (encoded via UTF-16).
    """
    units = text.encode("utf-16-le")
    codes = [units[i] | (units[i + 1] << 8) for i in range(0, len(units), 2)]
    if not codes:
        return True
    events = (_INPUT * (len(codes) * 2))()
    for i, code in enumerate(codes):
        down = events[i * 2]
        down.type = _INPUT_KEYBOARD
        down.ki = _KEYBDINPUT(0, code, _KEYEVENTF_UNICODE, 0, 0)
        up = events[i * 2 + 1]
        up.type = _INPUT_KEYBOARD
        up.ki = _KEYBDINPUT(0, code, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, 0, 0)

    if len(codes) <= _PACE_THRESHOLD_CHARS:
        sent = user32.SendInput(len(events), events, ctypes.sizeof(_INPUT))
        return sent == len(events)

    batch_events = _BATCH_CHARS * 2
    sent_total = 0
    for start in range(0, len(events), batch_events):
        chunk = events[start:start + batch_events]
        batch = (_INPUT * len(chunk))(*chunk)
        sent_total += user32.SendInput(len(batch), batch, ctypes.sizeof(_INPUT))
        time.sleep(_BATCH_PAUSE_SEC)
    return sent_total == len(events)


def insert(
    text: str,
    restore_clipboard: bool = True,
    target_hwnd: int = 0,
    method: str = "type",
) -> str:
    """Insert `text` into `target_hwnd` (the field focused when dictation began).

    `target_hwnd` is the window captured at recording start; focus is returned
    to it first so the text lands where the cursor was, even if WinDictoo's own
    window was clicked in between. `method` is "type" (SendInput Unicode,
    caret insertion, leaves the clipboard untouched) or "paste" (clipboard +
    Ctrl+V, more compatible with some apps). Returns a status key.
    """
    if not text:
        return "empty"

    # Return focus to the field the user was in when they started dictating.
    if target_hwnd and user32.IsWindow(target_hwnd):
        if not focus_window(target_hwnd):
            log.info("could not refocus target window; inserting into current focus")
        time.sleep(0.05)

    if method == "type":
        if type_unicode(text):
            log.info("inserted %d chars via typing", len(text))
            return "typed"
        log.info("typing failed, falling back to clipboard paste")

    # Clipboard + Ctrl+V path (primary when method='paste', else fallback).
    previous = get_text() if restore_clipboard else None
    if not set_text(text):
        log.warning("could not write to clipboard")
        return "clipboard_failed"
    after_write = sequence_number()

    try:
        _send_ctrl_v()
    except Exception as exc:  # noqa: BLE001
        log.warning("could not send Ctrl+V: %s", exc)
        return "clipboard_only"

    # Give the target app time to consume the clipboard before restoring.
    time.sleep(0.45)
    if previous is not None and sequence_number() == after_write:
        set_text(previous)
        log.debug("clipboard restored")

    log.info("inserted %d chars via paste", len(text))
    return "pasted"
