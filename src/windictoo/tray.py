"""System-tray presence: a coloured mic dot reflecting the session state."""

from __future__ import annotations

import logging
from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw

from .app import Dictation, State

log = logging.getLogger(__name__)

_COLORS: dict[State, tuple[int, int, int]] = {
    State.IDLE: (120, 120, 130),
    State.RECORDING: (220, 60, 60),
    State.TRANSCRIBING: (70, 130, 220),
    State.REFINING: (150, 90, 210),
    State.INSERTING: (70, 130, 220),
    State.DONE: (70, 180, 90),
    State.CANCELLED: (120, 120, 130),
    State.ERROR: (230, 150, 40),
}

_LABELS: dict[State, str] = {
    State.IDLE: "Готов",
    State.RECORDING: "Слушаю…",
    State.TRANSCRIBING: "Распознавание…",
    State.REFINING: "Улучшение…",
    State.INSERTING: "Вставка…",
    State.DONE: "Готово",
    State.CANCELLED: "Отменено",
    State.ERROR: "Ошибка",
}


def _icon(state: State) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _COLORS.get(state, (120, 120, 130))
    d.rounded_rectangle([24, 10, 40, 40], radius=8, fill=c)
    d.arc([16, 26, 48, 50], start=0, end=180, fill=c, width=5)
    d.line([32, 48, 32, 56], fill=c, width=5)
    d.line([22, 56, 42, 56], fill=c, width=5)
    return img


class Tray:
    def __init__(
        self,
        dictation: Dictation,
        on_show: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.dictation = dictation
        self.icon = pystray.Icon(
            "windictoo",
            _icon(State.IDLE),
            "WinDictoo — Готов",
            menu=pystray.Menu(
                pystray.MenuItem("Открыть WinDictoo", lambda: on_show(), default=True),
                pystray.MenuItem(lambda _: f"Статус: {_LABELS[self.dictation.state]}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Отменить диктовку", lambda: self.dictation.cancel()),
                pystray.MenuItem("Настройки", lambda: on_settings()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выход", lambda: on_quit()),
            ),
        )
        # Chain into any GUI state handler set later without clobbering it.
        self._prev = dictation.on_state_change
        dictation.on_state_change = self._on_state

    def _on_state(self, state: State) -> None:
        if self._prev is not None:
            try:
                self._prev(state)
            except Exception:  # noqa: BLE001
                log.exception("chained state handler failed")
        try:
            self.icon.icon = _icon(state)
            label = _LABELS.get(state, str(state))
            msg = self.dictation.message
            self.icon.title = f"WinDictoo — {label}" + (f": {msg}" if msg else "")
        except Exception:  # noqa: BLE001
            log.exception("tray update failed")
