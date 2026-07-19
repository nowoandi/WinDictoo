"""Global hotkey with press *and* release events.

pynput's GlobalHotKeys only reports activation, but press-and-hold needs the
release edge too, so the modifier state is tracked manually here.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from pynput import keyboard

log = logging.getLogger(__name__)

# Each modifier maps to the set of concrete keys that satisfy it, so a
# left/right Alt or the generic form all count.
_MODIFIER_ALIASES: dict[str, set] = {
    "ctrl": {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
    "alt": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr},
    "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
    "win": {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r},
}

_NAMED_KEYS = {
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc,
    **{f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 13)},
}

# --- Windows virtual-key codes for low-level suppression ---------------------
_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_SYSKEYDOWN = 0x0104
_WM_SYSKEYUP = 0x0105

# Each modifier maps to the concrete VKs (generic + left/right) that satisfy it.
_MOD_VK_GROUPS: dict[str, frozenset[int]] = {
    "ctrl": frozenset({0x11, 0xA2, 0xA3}),
    "alt": frozenset({0x12, 0xA4, 0xA5}),
    "shift": frozenset({0x10, 0xA0, 0xA1}),
    "win": frozenset({0x5B, 0x5C}),
}
_ALL_MOD_VKS = frozenset().union(*_MOD_VK_GROUPS.values())
_NAMED_VK = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B}


def token_to_vk(token: str) -> int | None:
    """Windows virtual-key code for a hotkey token ('space', 'f9', 'a', '1')."""
    t = token.lower()
    if t in _NAMED_VK:
        return _NAMED_VK[t]
    if len(t) >= 2 and t[0] == "f" and t[1:].isdigit():
        n = int(t[1:])
        if 1 <= n <= 12:
            return 0x70 + (n - 1)
    if len(t) == 1:
        return ord(t.upper())
    return None


def parse(spec: list[str]) -> tuple[list[str], object]:
    """Split ["ctrl","alt","space"] into (["ctrl","alt"], Key.space)."""
    mods = [s for s in spec if s in _MODIFIER_ALIASES]
    rest = [s for s in spec if s not in _MODIFIER_ALIASES]
    if not rest:
        raise ValueError(f"hotkey {spec} has no main key")
    name = rest[-1].lower()
    if name in _NAMED_KEYS:
        return mods, _NAMED_KEYS[name]
    if len(name) == 1:
        return mods, keyboard.KeyCode.from_char(name)
    raise ValueError(f"unsupported key: {name}")


def describe(spec: list[str]) -> str:
    return " + ".join(s.capitalize() for s in spec)


class HotkeyListener:
    def __init__(
        self,
        spec: list[str],
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_cancel: Callable[[], None],
        suppress: bool = True,
    ) -> None:
        self.spec = spec
        self.mods, self.main = parse(spec)
        self._on_press = on_press
        self._on_release = on_release
        self._on_cancel = on_cancel
        self._active = False
        self._main_suppressed = False
        self._listener: keyboard.Listener | None = None

        # Low-level suppression: swallow the main key while the combo is held
        # so it never reaches the focused app (otherwise holding e.g. Space
        # types spaces / moves the caret). Only enabled when the hotkey has at
        # least one modifier, so we never eat a bare printable key.
        self._main_vk = token_to_vk(self.spec[-1])
        self._mod_groups = [_MOD_VK_GROUPS[m] for m in self.mods]
        self._down_vks: set[int] = set()
        self._suppress = suppress and bool(self.mods) and self._main_vk is not None

    def _mods_vk_down(self) -> bool:
        return all(bool(g & self._down_vks) for g in self._mod_groups)

    def _fire(self, fn) -> None:
        # Run the callback off the hook thread: dictation.start() opens an
        # audio stream, and a slow low-level hook callback would be dropped
        # by Windows (LowLevelHooksTimeout).
        def run() -> None:
            try:
                fn()
            except Exception:  # noqa: BLE001
                log.exception("hotkey handler failed")

        threading.Thread(target=run, daemon=True).start()

    def _win32_filter(self, msg, data) -> None:
        """Runs for every key event on the hook thread. Detects the combo by
        virtual-key code, drives the press/release callbacks, and swallows the
        main key so it never reaches the focused application.

        Because pynput does NOT dispatch on_press/on_release for a suppressed
        event, all hotkey logic lives here rather than in those callbacks.
        """
        suppress = False
        try:
            vk = data.vkCode
            down = msg in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
            up = msg in (_WM_KEYUP, _WM_SYSKEYUP)

            if vk in _ALL_MOD_VKS:
                if down:
                    self._down_vks.add(vk)
                elif up:
                    self._down_vks.discard(vk)
                    # A modifier released ends an active hold, but keep
                    # swallowing the main key until it is physically released
                    # so no stray characters leak.
                    if self._active and not self._mods_vk_down():
                        self._active = False
                        self._fire(self._on_release)
            elif vk == 0x1B and down and self._active:  # Esc cancels
                self._fire(self._on_cancel)
            elif vk == self._main_vk:
                if down:
                    if self._main_suppressed or self._mods_vk_down():
                        if not self._active:
                            self._active = True
                            self._fire(self._on_press)
                        self._main_suppressed = True
                        suppress = self._suppress
                elif up:
                    if self._main_suppressed:
                        suppress = self._suppress
                    self._main_suppressed = False
                    if self._active:
                        self._active = False
                        self._fire(self._on_release)
        except Exception:  # noqa: BLE001 - the filter must never crash the hook
            log.exception("hotkey filter error")

        # suppress_event() raises to signal pynput; keep it outside the try so
        # the marker exception is not swallowed.
        if suppress:
            self._listener.suppress_event()

    def start(self) -> None:
        self._listener = keyboard.Listener(win32_event_filter=self._win32_filter)
        self._listener.start()
        log.info(
            "hotkey registered: %s (suppress=%s)", describe(self.spec), self._suppress
        )

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
