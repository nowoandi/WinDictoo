"""Entry point: launches the graphical WinDictoo application.

Run windowed (no console) via pythonw, or `python -m windictoo` / the `windictoo`
script for a console with logs.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading

from .app import Dictation
from .config import CONFIG_DIR, LOG_PATH, Config
from .hotkey import HotkeyListener, describe


def setup_logging(verbose: bool = False) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
    # pythonw has no console; sys.stdout is None there, so only add a stream
    # handler when one actually exists.
    if sys.stdout is not None:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )

    # Catch otherwise-invisible crashes (windowed .exe has no console): both
    # the main thread and worker threads.
    log = logging.getLogger("windictoo")

    def _hook(exc_type, exc, tb):
        log.error("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook

    def _thread_hook(args):
        log.error("UNCAUGHT THREAD EXCEPTION",
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = _thread_hook


class HotkeyController:
    """Owns the current listener so the GUI can swap the combo live."""

    def __init__(self, dictation: Dictation, cfg: Config) -> None:
        self.dictation = dictation
        self.cfg = cfg
        self.listener: HotkeyListener | None = None

    def apply(self, spec: list[str]) -> str | None:
        """(Re)register the hotkey. Returns None on success, else an error."""
        old = self.listener
        try:
            new = HotkeyListener(
                spec,
                on_press=self.dictation.on_hotkey_down,
                on_release=self.dictation.on_hotkey_up,
                on_cancel=self.dictation.cancel,
                suppress=self.cfg.suppress_hotkey,
            )
            new.start()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("windictoo").warning("hotkey %s failed: %s", spec, exc)
            return f"Не удалось назначить {describe(spec)}: {exc}"
        if old is not None:
            old.stop()
        self.listener = new
        return None

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None


_instance_mutex = None


def _acquire_single_instance():
    """Return a held mutex handle if this is the first instance, else None."""
    import ctypes

    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "WinDictoo_SingleInstance_Mutex")
    if not handle or kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def main() -> int:
    p = argparse.ArgumentParser(prog="windictoo", description="Локальный голосовой ввод")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--preload", action="store_true", help="загрузить модель при старте")
    p.add_argument("--tray-only", action="store_true", help="старт свёрнутым в трей")
    args = p.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("windictoo")

    # Single instance: if WinDictoo is already running, ask it to show its window
    # (drop a flag it polls for) and exit instead of starting a duplicate.
    global _instance_mutex
    _instance_mutex = _acquire_single_instance()
    if _instance_mutex is None:
        from .config import SHOW_FLAG

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            SHOW_FLAG.write_text("1", encoding="utf-8")
        except OSError:
            pass
        log.info("WinDictoo уже запущен — показываю существующее окно")
        return 0

    cfg = Config.load()
    cfg.save()
    dictation = Dictation(cfg)

    from .gui import WinDictooGUI

    controller = HotkeyController(dictation, cfg)

    stop = threading.Event()

    def on_quit() -> None:
        controller.stop()
        dictation.cancel()
        if tray is not None:
            try:
                tray.icon.stop()
            except Exception:  # noqa: BLE001
                pass
        stop.set()
        log.info("WinDictoo остановлен")

    gui = WinDictooGUI(cfg, dictation, apply_hotkey=controller.apply, on_quit=on_quit,
                    stop_hotkey=controller.stop)

    # Tray runs detached in its own thread; its menu marshals to the GUI.
    from .tray import Tray

    tray = Tray(
        dictation,
        on_show=lambda: gui.root.after(0, gui.show),
        on_settings=lambda: gui.root.after(0, gui.open_settings),
        on_quit=lambda: gui.root.after(0, gui.quit),
    )
    tray.icon.run_detached()

    err = controller.apply(cfg.hotkey)
    if err:
        log.warning(err)

    log.info("WinDictoo запущен. Горячая клавиша: %s (режим: %s)", describe(cfg.hotkey), cfg.mode)

    # Always warm the model in the background (short delay keeps the window
    # snappy while it appears): the first dictation then starts instantly
    # instead of silently stalling on the model load.
    gui.root.after(1500, gui.preload_model_async)
    if args.tray_only:
        gui.hide_to_tray()

    # First run: show the setup wizard once the event loop is up.
    if not cfg.onboarding_done and not args.tray_only:
        from .onboarding import Onboarding

        def show_wizard() -> None:
            Onboarding(gui.root, cfg, dictation, controller.apply, on_finish=lambda: gui.show(),
                       stop_hotkey=controller.stop)

        gui.root.after(300, show_wizard)

    gui.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
