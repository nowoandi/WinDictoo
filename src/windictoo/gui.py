"""Modern CustomTkinter application: main window, settings, overlay.

tkinter/CTk owns the main thread; the tray icon runs detached and the hotkey
listener runs in its own thread. Cross-thread UI updates hop back onto the UI
thread with ``after``.
"""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk

import customtkinter as ctk

from . import autostart, insert as _insert, refine, theme, update
from .app import Dictation, State
from .audio import input_devices
from .config import CONFIG_DIR, LOG_PATH, Config
from .hotkey import describe
from .transcribe import Transcriber
from .widgets import Equalizer, MicIndicator

log = logging.getLogger(__name__)

MODELS = ["tiny", "base", "small", "medium", "large-v3"]
LANGS = [("Автоопределение", "auto"), ("Русский", "ru"), ("English", "en"), ("Deutsch", "de")]

_MOD_KEYSYMS = {
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift",
    "Super_L": "win", "Super_R": "win",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


class WinDictooGUI:
    def __init__(self, cfg, dictation, apply_hotkey, on_quit, stop_hotkey=None) -> None:
        self.cfg = cfg
        self.dictation = dictation
        self.apply_hotkey = apply_hotkey
        # Pauses the global hotkey during capture so its suppressed main key
        # (e.g. Space) can still reach the capture field.
        self.stop_hotkey = stop_hotkey
        self._on_quit = on_quit
        # Set while quitting: state changes fired during shutdown (e.g. by
        # Dictation.cancel) must not touch the dying tk mainloop.
        self._closing = False

        theme.apply(cfg.ui_theme)
        ctk.set_appearance_mode(theme.APPEARANCE)

        self.root = ctk.CTk()
        self.root.title("WinDictoo")
        W, H = 420, 620
        self.root.minsize(400, 580)
        # Open centred on the screen instead of the OS default corner.
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - W) // 2)
        y = max(0, (sh - H) // 2 - 20)
        self.root.geometry(f"{W}x{H}+{x}+{y}")
        self.root.configure(fg_color=theme.BG)

        self._update_banner: ctk.CTkButton | None = None
        self._update_info: update.UpdateInfo | None = None
        self.settings_win: ctk.CTkToplevel | None = None
        self.overlay: tk.Toplevel | None = None
        self._ov_dot = None
        self._ov_label = None
        self._ov_msg = None
        self._ov_eq = None
        self._ov_stop = None

        # Log exceptions raised inside tk callbacks — a windowed .exe has no
        # console, so otherwise they would vanish silently.
        self.root.report_callback_exception = self._log_ui_error

        self._build()
        dictation.on_state_change = self._on_state
        dictation.is_own_window = lambda h: _insert.window_pid(h) == os.getpid()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        # A second launch drops a flag instead of starting a duplicate; watch
        # for it and bring this (single) window to the front.
        self._poll_show_flag()

    def _log_ui_error(self, exc, val, tb) -> None:
        import traceback

        log.error("UI callback error:\n%s", "".join(traceback.format_exception(exc, val, tb)))

    def _poll_show_flag(self) -> None:
        from .config import SHOW_FLAG

        try:
            if SHOW_FLAG.exists():
                SHOW_FLAG.unlink(missing_ok=True)
                self.show()
        except OSError:
            pass
        except Exception:  # noqa: BLE001
            # A stale widget reference must not silently kill the poll loop
            # forever — that would strand the window hidden until restart.
            log.exception("show-flag handling failed")
        finally:
            try:
                self.root.after(700, self._poll_show_flag)
            except RuntimeError:
                pass  # mainloop already stopped (shutdown)

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        # Header: title on the left, theme toggle + settings on the right.
        # (No custom minimise button — the native title-bar one already does
        # that.)
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 6))
        ctk.CTkButton(header, text="⋮", width=40, height=40, corner_radius=theme.RADIUS_WIDGET,
                      border_width=1, border_color=theme.STROKE,
                      font=_font(20, "bold"), fg_color=theme.CARD, hover_color=theme.CARD_HI,
                      text_color=theme.TEXT, command=self.open_settings).pack(side="right")
        theme_icon = "☀" if self.cfg.ui_theme == "dark" else "🌙"
        ctk.CTkButton(header, text=theme_icon, width=40, height=40, corner_radius=theme.RADIUS_WIDGET,
                      border_width=1, border_color=theme.STROKE,
                      font=_font(16), fg_color=theme.CARD, hover_color=theme.CARD_HI,
                      text_color=theme.TEXT, command=self._toggle_theme).pack(side="right", padx=(0, 8))
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(side="left")
        ctk.CTkLabel(title_row, text="WinDictoo", font=_font(24, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        from . import __version__

        ctk.CTkLabel(title_row, text=f"v{__version__}", font=_font(10),
                     text_color=theme.MUTED).pack(side="left", padx=(6, 0), pady=(10, 0))

        # Hero card. The mic is clickable — it starts/stops dictation.
        hero = ctk.CTkFrame(self.root, fg_color=theme.CARD, corner_radius=theme.RADIUS_CONTAINER,
                            border_width=1, border_color=theme.STROKE)
        hero.pack(fill="x", padx=20, pady=8)
        self.hero_frame = hero
        if self._update_info is not None:
            # A theme switch destroys and rebuilds every widget; keep the
            # banner alive across that rebuild instead of losing it silently.
            self._update_banner = None
            self._show_update_banner(self._update_info)
        self.mic = MicIndicator(hero, size=118, bg=theme.CARD)
        self.mic.pack(pady=(20, 4))
        self.mic.bind("<Button-1>", lambda e: self._toggle_dictation())
        self.mic.configure(cursor="hand2")
        self.status_lbl = ctk.CTkLabel(hero, text=theme.STATE_LABEL[State.IDLE],
                                       font=_font(17, "bold"), text_color=theme.TEXT)
        self.status_lbl.pack()
        self.eq = Equalizer(hero, width=250, height=38, bg=theme.CARD)
        self.eq.pack(pady=(4, 2))
        self.sub_lbl = ctk.CTkLabel(hero, text="", font=_font(11), text_color=theme.MUTED,
                                    wraplength=340)
        self.sub_lbl.pack(pady=(0, 16))

        # Chips row
        chips = ctk.CTkFrame(self.root, fg_color="transparent")
        chips.pack(fill="x", padx=20, pady=(0, 4))
        self.hotkey_chip = self._chip(chips, "⌨ " + describe(self.cfg.hotkey))
        self.model_chip = self._chip(chips, "◈ " + self.cfg.model)
        self.mode_chip = self._chip(chips, "⏱ " + ("удержание" if self.cfg.mode == "hold" else "переключ."))

        # Primary Start/Stop button (label toggles with state).
        self.test_btn = ctk.CTkButton(self.root, text="▶   Старт", height=48,
                                      corner_radius=theme.RADIUS_BUTTON, font=_font(15, "bold"),
                                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                      command=self._toggle_dictation)
        self.test_btn.pack(fill="x", padx=20, pady=(10, 4))

        # Result card (roomy, so the recognized text is always visible)
        self.result_card = ctk.CTkFrame(self.root, fg_color=theme.CARD,
                                        corner_radius=theme.RADIUS_CONTAINER,
                                        border_width=1, border_color=theme.STROKE)
        self.result_card.pack(fill="both", expand=True, padx=20, pady=(8, 18))
        rhead = ctk.CTkFrame(self.result_card, fg_color="transparent")
        rhead.pack(fill="x", padx=16, pady=(10, 2))
        ctk.CTkLabel(rhead, text="РАСПОЗНАННЫЙ ТЕКСТ", font=_font(10, "bold"),
                     text_color=theme.MUTED).pack(side="left")
        self.copy_btn = ctk.CTkButton(rhead, text="⧉ Копировать", width=110, height=28,
                                      corner_radius=theme.RADIUS_WIDGET, font=_font(11, "bold"),
                                      fg_color=theme.CARD_HI, hover_color=theme.STROKE,
                                      text_color=theme.ACCENT_HOVER, border_width=1,
                                      border_color=theme.STROKE, command=self._copy_result)
        self.copy_btn.pack(side="right")
        # Read-only but selectable, so Ctrl+C works (a disabled textbox can be
        # neither selected nor copied).
        self.result_box = ctk.CTkTextbox(self.result_card, font=_font(13), fg_color=theme.CARD_HI,
                                         text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                                         wrap="word", border_width=1, border_color=theme.STROKE, height=80)
        self.result_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.result_box.insert("1.0", "Нажмите Старт или микрофон и продиктуйте…")
        self.result_box.bind("<Key>", self._readonly_key)

    def _chip(self, parent, text: str) -> ctk.CTkLabel:
        f = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=theme.RADIUS_CHIP,
                         border_width=1, border_color=theme.STROKE)
        f.pack(side="left", padx=(0, 8))
        lbl = ctk.CTkLabel(f, text=text, font=_font(11), text_color=theme.MUTED)
        lbl.pack(padx=12, pady=6)
        return lbl

    def _refresh_chips(self) -> None:
        self.hotkey_chip.configure(text="⌨  " + describe(self.cfg.hotkey))
        self.model_chip.configure(text="◈  " + self.cfg.model)
        self.mode_chip.configure(text="⏱  " + ("удержание" if self.cfg.mode == "hold" else "переключение"))
        self.root.update_idletasks()

    # ------------------------------------------------------------ state/render

    def _on_state(self, state: State) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._render(state))
        except RuntimeError:
            pass  # mainloop already stopped (shutdown race)

    def _render(self, state: State) -> None:
        label = theme.STATE_LABEL.get(state, str(state))
        # The first transcription silently pays the model-load cost, which
        # looks like a hang — name what is actually happening.
        if state is State.TRANSCRIBING and not self.dictation.transcriber.is_loaded:
            label = "Загружаю модель…"
        self.status_lbl.configure(text=label,
                                  text_color=theme.STATE_COLOR.get(state, theme.TEXT))
        self.mic.set_state(state)
        self.sub_lbl.configure(text=self.dictation.message or self._default_sub(state))
        self.eq.set_active(state is State.RECORDING)
        # Button reflects what a click will do next.
        if state is State.RECORDING:
            self.test_btn.configure(text="⏹   Стоп", fg_color=theme.DANGER, hover_color="#e03e5c")
        elif state is State.IDLE:
            self.test_btn.configure(text="▶   Старт", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER)
        else:
            self.test_btn.configure(text="…   " + theme.STATE_LABEL.get(state, ""),
                                    fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER)
        if state is State.RECORDING:
            self._pump_level()
        self._render_overlay(state)

    def _default_sub(self, state: State) -> str:
        if state in (State.RECORDING, State.TRANSCRIBING, State.REFINING):
            return "Esc — отмена"
        return ""

    def _pump_level(self) -> None:
        if self.dictation.state is State.RECORDING:
            lvl = self.dictation.recorder.level
            self.eq.set_level(lvl)
            if self._ov_eq is not None:
                self._ov_eq.set_level(lvl)
            self.root.after(50, self._pump_level)
        else:
            self.eq.set_active(False)

    def _show_result(self, text: str) -> None:
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text or "(пусто)")

    # Allow selection, copy (Ctrl+C) and select-all (Ctrl+A); block edits.
    def _readonly_key(self, event):
        if event.state & 0x4:  # Control held → copy / select-all
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End",
                             "Prior", "Next", "Shift_L", "Shift_R"):
            return None
        return "break"

    def _copy_result(self) -> None:
        text = self.result_box.get("1.0", "end").strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.copy_btn.configure(text="Скопировано ✓")
        self.root.after(1500, lambda: self.copy_btn.configure(text="⧉ Копировать"))

    # ---------------------------------------------------------------- overlay

    def _render_overlay(self, state: State) -> None:
        if state is State.IDLE:
            if self.overlay is not None:
                self.overlay.withdraw()
            return
        if self.overlay is None:
            self._build_overlay()
        self.overlay.deiconify()
        self._position_overlay(self.overlay)
        self.overlay.lift()
        self._ov_dot.delete("all")
        col = theme.STATE_COLOR.get(state, theme.ACCENT)
        self._ov_dot.create_oval(3, 3, 21, 21, fill=col, outline="")
        self._ov_label.configure(text=theme.STATE_LABEL.get(state, ""))
        self._ov_msg.configure(text=self.dictation.message or self._default_sub(state))
        self._ov_eq.set_active(state is State.RECORDING)
        self._draw_overlay_button(hover=False)

    def _build_overlay(self) -> None:
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.attributes("-topmost", True)
        w, h = 326, 82
        sw, sh = ov.winfo_screenwidth(), ov.winfo_screenheight()
        ov.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - 170}")
        self._ov_w, self._ov_h = w, h
        ov.configure(bg=theme.CARD)
        wrap = tk.Frame(ov, bg=theme.CARD)
        wrap.pack(fill="both", expand=True)
        row = tk.Frame(wrap, bg=theme.CARD)
        row.pack(fill="both", expand=True, padx=16, pady=11)

        self._ov_dot = tk.Canvas(row, width=24, height=24, bg=theme.CARD, highlightthickness=0)
        self._ov_dot.pack(side="left", padx=(2, 10))
        # Stop button — far right; equalizer to its left with a clear gap.
        stop = tk.Canvas(row, width=40, height=40, bg=theme.CARD, highlightthickness=0, cursor="hand2")
        self._ov_stop = stop
        self._draw_overlay_button(hover=False)
        stop.bind("<Button-1>", lambda e: self._overlay_stop())
        stop.bind("<Enter>", lambda e: self._draw_overlay_button(hover=True))
        stop.bind("<Leave>", lambda e: self._draw_overlay_button(hover=False))
        stop.pack(side="right", padx=(0, 2))
        self._ov_eq = Equalizer(row, width=54, height=40, bars=7, bg=theme.CARD)
        self._ov_eq.pack(side="right", padx=(0, 14))
        col = tk.Frame(row, bg=theme.CARD)
        col.pack(side="left", fill="both", expand=True)
        self._ov_label = tk.Label(col, text="", bg=theme.CARD, fg=theme.TEXT,
                                  font=("Segoe UI", 12, "bold"), anchor="w")
        self._ov_label.pack(anchor="w")
        self._ov_msg = tk.Label(col, text="", bg=theme.CARD, fg=theme.MUTED,
                                font=("Segoe UI", 9), anchor="w")
        self._ov_msg.pack(anchor="w")

        for wgt in (wrap, row, col, self._ov_label, self._ov_msg, self._ov_dot):
            wgt.bind("<Button-1>", self._ov_drag_start)
            wgt.bind("<B1-Motion>", self._ov_drag_move)
        self.overlay = ov
        # Round the window itself via the Win32 region API (stable, unlike a
        # transparent-colour key which can destabilise a borderless window).
        self.root.after(30, lambda: self._round_window(ov, w, h))

    def _position_overlay(self, ov) -> None:
        """Centre the overlay near the bottom of the desktop, just above the
        taskbar. Positions the real window via SetWindowPos (physical pixels)
        because tk's geometry multiplies by the DPI scale and pushes it off."""
        try:
            import ctypes

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            u = ctypes.windll.user32
            ov.update_idletasks()
            hwnd = u.GetAncestor(ov.winfo_id(), 2) or ov.winfo_id()
            work = RECT()
            u.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
            win = RECT()
            u.GetWindowRect(hwnd, ctypes.byref(win))
            ww, hh = win.right - win.left, win.bottom - win.top
            x = work.left + (work.right - work.left - ww) // 2
            y = work.bottom - hh - 12
            # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
            u.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, 0x0001 | 0x0004 | 0x0010)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _round_window(ov, w, h, r=32) -> None:
        try:
            import ctypes

            # GA_ROOT (2) gives the real top-level HWND of the borderless window.
            hwnd = ctypes.windll.user32.GetAncestor(ov.winfo_id(), 2)
            if not hwnd:
                hwnd = ov.winfo_id()
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:  # noqa: BLE001
            pass

    def _draw_overlay_button(self, hover: bool = False) -> None:
        # Green button that reflects the state: a stop glyph while recording,
        # a check mark once the recording has been stopped/processed.
        c = self._ov_stop
        if c is None:
            return
        c.delete("all")
        if self.dictation.state is State.RECORDING:
            col = theme.ACCENT_HOVER if hover else theme.ACCENT
            c.create_oval(3, 3, 37, 37, fill=col, outline="")
            c.create_text(20, 20, text="■", fill="#ffffff", font=("Segoe UI", 13))
        else:
            c.create_oval(3, 3, 37, 37, fill=theme.SUCCESS, outline="")
            c.create_text(21, 19, text="✓", fill="#ffffff", font=("Segoe UI", 16, "bold"))

    def _ov_drag_start(self, e) -> None:
        self._ov_drag = (e.x_root, e.y_root, self.overlay.winfo_x(), self.overlay.winfo_y())

    def _ov_drag_move(self, e) -> None:
        if not hasattr(self, "_ov_drag"):
            return
        sx, sy, ox, oy = self._ov_drag
        self.overlay.geometry(f"+{ox + e.x_root - sx}+{oy + e.y_root - sy}")

    def _overlay_stop(self) -> None:
        # Only the recording state is stoppable; after that the button is a
        # non-interactive "done" check.
        if self.dictation.state is State.RECORDING:
            self.dictation.stop_and_process()

    # ----------------------------------------------------------------- theme

    def _toggle_theme(self) -> None:
        self.set_theme("light-green" if self.cfg.ui_theme == "dark" else "dark")

    def set_theme(self, name: str) -> None:
        if name not in theme.PALETTES or name == self.cfg.ui_theme:
            return
        self.cfg.ui_theme = name
        self.cfg.save()
        # Defer well past CustomTkinter's own click/focus after-callbacks so
        # we never destroy a widget while CTk still has a pending focus_set on
        # it (that raised a TclError before).
        try:
            self.root.focus_set()
        except tk.TclError:
            pass
        self.root.after(140, self._rebuild_for_theme)

    def _rebuild_for_theme(self) -> None:
        try:
            theme.apply(self.cfg.ui_theme)
            ctk.set_appearance_mode(theme.APPEARANCE)
            self.root.configure(fg_color=theme.BG)
            if self.settings_win is not None and self.settings_win.winfo_exists():
                self.settings_win.destroy()
                self.settings_win = None
            if self.overlay is not None:
                self.overlay.destroy()
                self.overlay = None
                self._ov_eq = None
            for w in list(self.root.winfo_children()):
                try:
                    w.destroy()
                except tk.TclError:
                    pass
            self._build()
            self._render(self.dictation.state)
        except Exception:  # noqa: BLE001
            log.exception("theme rebuild failed")

    # -------------------------------------------------------------- dictation

    def _toggle_dictation(self) -> None:
        """Start recording, or stop-and-transcribe if already recording.
        The recognized text is shown in the result box (the app window has
        focus, so it is not inserted into another app)."""
        if self.dictation.state is State.RECORDING:
            self.dictation.stop_and_process()
            return
        if self.dictation.state is not State.IDLE:
            return
        self._show_result("Слушаю…")

        def sink(text: str) -> None:
            self.root.after(0, lambda: self._show_result(text))
            self.dictation.sink = None

        self.dictation.sink = sink
        self.dictation.start()

    # --------------------------------------------------------------- settings

    def open_settings(self) -> None:
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.deiconify()
            self.settings_win.lift()
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Настройки WinDictoo")
        win.geometry("560x830")
        win.configure(fg_color=theme.BG)
        win.transient(self.root)
        self.settings_win = win
        tabs = ctk.CTkTabview(win, fg_color=theme.CARD, segmented_button_fg_color=theme.CARD,
                              segmented_button_selected_color=theme.ACCENT,
                              segmented_button_selected_hover_color=theme.ACCENT_HOVER,
                              corner_radius=theme.RADIUS_CARD,
                              border_width=1, border_color=theme.STROKE)
        tabs.pack(fill="both", expand=True, padx=16, pady=16)
        for name in ("Основные", "Распознавание", "Улучшение", "Приватность"):
            tabs.add(name)
        self._tab_general(tabs.tab("Основные"))
        self._tab_transcription(tabs.tab("Распознавание"))
        self._tab_refinement(tabs.tab("Улучшение"))
        self._tab_privacy(tabs.tab("Приватность"))

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=theme.CARD_HI, corner_radius=theme.RADIUS_CARD,
                             border_width=1, border_color=theme.STROKE)
        outer.pack(fill="x", padx=6, pady=7)
        ctk.CTkLabel(outer, text=title.upper(), font=_font(10, "bold"),
                     text_color=theme.MUTED).pack(anchor="w", padx=14, pady=(10, 2))
        return outer

    def _tab_general(self, tab) -> None:
        c1 = self._card(tab, "Горячая клавиша")
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(row, text="Сочетание", font=_font(13), text_color=theme.TEXT).pack(side="left")
        self.hk_btn = ctk.CTkButton(row, text=describe(self.cfg.hotkey), width=170,
                                    corner_radius=theme.RADIUS_BUTTON,
                                    fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                    command=self._capture_hotkey)
        self.hk_btn.pack(side="right")
        self.hk_err = ctk.CTkLabel(c1, text="", font=_font(11), text_color=theme.DANGER)
        self.hk_err.pack(anchor="w", padx=14)
        mode = ctk.CTkSegmentedButton(
            c1, values=["Удержание", "Переключение"],
            corner_radius=theme.RADIUS_WIDGET,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            command=lambda v: self._set_mode("hold" if v == "Удержание" else "toggle"))
        mode.set("Удержание" if self.cfg.mode == "hold" else "Переключение")
        mode.pack(fill="x", padx=14, pady=(2, 12))
        sup = ctk.CTkSwitch(c1, text="Не пропускать клавишу в приложение (Пробел не двигает курсор)",
                            font=_font(12), progress_color=theme.ACCENT,
                            command=lambda: self._set_suppress(sup.get()))
        sup.select() if self.cfg.suppress_hotkey else sup.deselect()
        sup.pack(anchor="w", padx=14, pady=(0, 12))

        c2 = self._card(tab, "Куда вставлять текст")
        method = ctk.CTkSegmentedButton(
            c2, values=["Печать в поле", "Буфер (Ctrl+V)"],
            corner_radius=theme.RADIUS_WIDGET,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            command=lambda v: self._set_method("type" if v == "Печать в поле" else "paste"))
        method.set("Печать в поле" if self.cfg.insertion_method == "type" else "Буфер (Ctrl+V)")
        method.pack(fill="x", padx=14, pady=(2, 12))

        c_mic = self._card(tab, "Микрофон")
        devices = input_devices()
        mic_labels = ["Системный (по умолчанию)"] + [name for _, name in devices]
        current_label = next(
            (name for idx, name in devices if idx == self.cfg.input_device_index),
            "Системный (по умолчанию)",
        )
        mic_var = ctk.StringVar(value=current_label)
        ctk.CTkOptionMenu(c_mic, values=mic_labels, variable=mic_var, fg_color=theme.CARD,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          command=lambda v: self._set_input_device(v, devices)).pack(
            fill="x", padx=14, pady=(2, 6))
        ctk.CTkLabel(c_mic, text="Полезно, если в системе несколько микрофонов "
                     "(например, встроенный в ноутбук и гарнитура).",
                     font=_font(11), text_color=theme.MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        c_theme = self._card(tab, "Тема оформления")
        th = ctk.CTkSegmentedButton(
            c_theme, values=["Тёмная", "Светло-зелёная"],
            corner_radius=theme.RADIUS_WIDGET,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            command=lambda v: self.set_theme("dark" if v == "Тёмная" else "light-green"))
        th.set("Тёмная" if self.cfg.ui_theme == "dark" else "Светло-зелёная")
        th.pack(fill="x", padx=14, pady=(2, 12))

        c3 = self._card(tab, "Приложение")
        auto = ctk.CTkSwitch(c3, text="Запускать при входе в Windows", font=_font(12),
                             progress_color=theme.ACCENT)
        auto.select() if autostart.is_enabled() else auto.deselect()
        auto.configure(command=lambda: self._set_autostart(auto))
        auto.pack(anchor="w", padx=14, pady=(2, 12))

    def _tab_transcription(self, tab) -> None:
        c1 = self._card(tab, "Модель Whisper")
        mv = ctk.StringVar(value=self.cfg.model)
        # text_color must be explicit: CTk's default button text is white,
        # which vanishes on the white CARD background of the light theme.
        om = ctk.CTkOptionMenu(c1, values=MODELS, variable=mv, fg_color=theme.CARD,
                               text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                               button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                               command=lambda v: self._set_model(v))
        om.pack(fill="x", padx=14, pady=(2, 6))
        self.model_status = ctk.CTkLabel(c1, text="tiny/base — быстро · small — баланс · large-v3 — точнее",
                                         font=_font(11), text_color=theme.MUTED, wraplength=460)
        self.model_status.pack(anchor="w", padx=14)
        ctk.CTkButton(c1, text="Загрузить модель сейчас", corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=self._preload_model).pack(anchor="w", padx=14, pady=10)

        c2 = self._card(tab, "Параметры")
        lv = ctk.StringVar(value=next(l[0] for l in LANGS if l[1] == self.cfg.language))
        ctk.CTkLabel(c2, text="Язык речи", font=_font(12), text_color=theme.TEXT).pack(anchor="w", padx=14)
        ctk.CTkOptionMenu(c2, values=[l[0] for l in LANGS], variable=lv, fg_color=theme.CARD,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          command=lambda v: self._set_lang(v)).pack(fill="x", padx=14, pady=(2, 8))
        self.thr_lbl = ctk.CTkLabel(c2, text=f"Потоков CPU: {self.cfg.threads}", font=_font(12),
                                    text_color=theme.TEXT)
        self.thr_lbl.pack(anchor="w", padx=14)
        sl = ctk.CTkSlider(c2, from_=1, to=16, number_of_steps=15, progress_color=theme.ACCENT,
                           button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                           command=self._set_threads)
        sl.set(self.cfg.threads)
        sl.pack(fill="x", padx=14, pady=(2, 12))

        c3 = self._card(tab, "Память")
        unload = ctk.CTkSwitch(
            c3, text="Выгружать модель из ОЗУ при простое (>15 мин)", font=_font(12),
            progress_color=theme.ACCENT,
            command=lambda: self._set_unload_idle(unload.get()))
        unload.select() if self.cfg.unload_model_idle_min else unload.deselect()
        unload.pack(anchor="w", padx=14, pady=(2, 4))
        ctk.CTkLabel(c3, text="Освобождает 0.5–3 ГБ памяти на слабых ПК; следующая "
                     "диктовка после простоя снова платит цену загрузки модели.",
                     font=_font(11), text_color=theme.MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 12))

    def _tab_refinement(self, tab) -> None:
        c0 = self._card(tab, "Что это")
        ctk.CTkLabel(
            c0,
            text="Необязательная функция: локальная нейросеть (LLM) исправляет ошибки "
                 "распознавания и расставляет знаки препинания. Работает через бесплатную "
                 "программу Ollama — полностью на этом компьютере, без интернета.",
            font=_font(12), text_color=theme.TEXT, wraplength=470, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        cs = self._card(tab, "Как включить (нужно один раз)")
        for step in [
            "1.  Установите Ollama — кнопка ниже откроет официальный сайт.",
            "2.  Скачайте модель: вторая кнопка скопирует команду — вставьте её\n"
            "     в окно «Терминал» (Win+X → Терминал) и нажмите Enter.",
            "3.  Нажмите «Проверить» внизу — модель появится в статусе.",
            "4.  Включите переключатель «Улучшать текст…».",
        ]:
            ctk.CTkLabel(cs, text=step, font=_font(12), text_color=theme.TEXT,
                         wraplength=470, justify="left").pack(anchor="w", padx=14, pady=1)
        btns = ctk.CTkFrame(cs, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(8, 12))
        ctk.CTkButton(btns, text="🌐 Открыть сайт Ollama", corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=self._open_ollama_site).pack(side="left")
        self._pull_btn = ctk.CTkButton(btns, text="⧉ Скопировать команду модели",
                                       corner_radius=theme.RADIUS_BUTTON,
                                       fg_color=theme.CARD, hover_color=theme.CARD_HI,
                                       text_color=theme.TEXT, border_width=1,
                                       border_color=theme.STROKE,
                                       command=self._copy_pull_cmd)
        self._pull_btn.pack(side="left", padx=8)

        c1 = self._card(tab, "Настройки Ollama")
        en = ctk.CTkSwitch(c1, text="Улучшать текст локальной LLM", font=_font(12),
                           progress_color=theme.ACCENT, command=lambda: self._set_refine(en.get()))
        en.select() if self.cfg.refine_enabled else en.deselect()
        en.pack(anchor="w", padx=14, pady=(2, 8))
        ep = ctk.CTkEntry(c1, placeholder_text="http://127.0.0.1:11434", fg_color=theme.CARD,
                          corner_radius=theme.RADIUS_WIDGET, border_width=1, border_color=theme.STROKE)
        ep.insert(0, self.cfg.ollama_endpoint)
        ep.pack(fill="x", padx=14, pady=4)
        self.ollama_model = ctk.CTkEntry(c1, placeholder_text="модель, напр. qwen2.5:3b",
                                         fg_color=theme.CARD, corner_radius=theme.RADIUS_WIDGET,
                                         border_width=1, border_color=theme.STROKE)
        self.ollama_model.insert(0, self.cfg.ollama_model)
        self.ollama_model.pack(fill="x", padx=14, pady=4)
        self.ollama_status = ctk.CTkLabel(c1, text="", font=_font(11), text_color=theme.MUTED, wraplength=460)
        self.ollama_status.pack(anchor="w", padx=14, pady=2)

        def save() -> None:
            self.cfg.ollama_endpoint = ep.get()
            self.cfg.ollama_model = self.ollama_model.get()
            self.cfg.save()

        def check() -> None:
            save()
            self.ollama_status.configure(text="Проверка…")

            def work() -> None:
                names: list[str] = []
                try:
                    names = refine.list_models(ep.get())
                    msg = "Доступно: " + ", ".join(names) if names else \
                        "Ollama работает, но моделей нет — шаг 2 в инструкции выше."
                except refine.NonLocalEndpoint:
                    msg = "Адрес должен быть localhost."
                except Exception as exc:  # noqa: BLE001
                    msg = f"Ollama не запущена или не установлена: {exc}"

                def apply() -> None:
                    self.ollama_status.configure(text=msg)
                    # Convenience: fill the model field with the first found
                    # model so a novice doesn't have to type it by hand.
                    if names and not self.ollama_model.get().strip():
                        self.ollama_model.insert(0, names[0])
                        self.cfg.ollama_model = names[0]
                        self.cfg.save()

                self.root.after(0, apply)

            threading.Thread(target=work, daemon=True).start()

        ctk.CTkButton(c1, text="Проверить", corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=check).pack(anchor="w", padx=14, pady=10)

    def _tab_privacy(self, tab) -> None:
        c1 = self._card(tab, "Как WinDictoo обращается с данными")
        for p in [
            "Звук обрабатывается только на этом компьютере.",
            "Без облака, аккаунтов и ключей API.",
            "Аудио не сохраняется на диск.",
            "Ollama — только localhost.",
            "Нет аналитики и телеметрии.",
        ]:
            ctk.CTkLabel(c1, text="✓  " + p, font=_font(12), text_color=theme.TEXT,
                         wraplength=470, justify="left").pack(anchor="w", padx=14, pady=2)
        ctk.CTkFrame(c1, height=6, fg_color="transparent").pack()

        c2 = self._card(tab, "Диагностика")
        for text, cmd in [
            ("Показать мастер настройки снова", self.open_onboarding),
            ("Открыть журнал", self._open_log),
            ("Открыть папку настроек", self._open_config_dir),
        ]:
            ctk.CTkButton(c2, text=text, fg_color=theme.CARD, hover_color=theme.CARD_HI,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_BUTTON,
                          border_width=1, border_color=theme.STROKE,
                          anchor="w", command=cmd).pack(fill="x", padx=14, pady=4)
        ctk.CTkFrame(c2, height=6, fg_color="transparent").pack()

        c3 = self._card(tab, "О программе")
        from . import __version__

        ctk.CTkLabel(c3, text=f"WinDictoo {__version__}", font=_font(13, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=14, pady=(0, 2))
        ctk.CTkLabel(c3, text="Открытый код, лицензия MIT — свободно для любого "
                     "использования, изменения и распространения.",
                     font=_font(12), text_color=theme.TEXT, wraplength=470,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        ctk.CTkButton(c3, text="🌐 Открыть на GitHub", fg_color=theme.CARD,
                      hover_color=theme.CARD_HI, text_color=theme.TEXT,
                      corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=theme.STROKE,
                      anchor="w", command=self._open_github).pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkButton(c3, text="🔄 Проверить обновления", fg_color=theme.CARD,
                      hover_color=theme.CARD_HI, text_color=theme.TEXT,
                      corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=theme.STROKE,
                      anchor="w",
                      command=lambda: self.check_update_async(force=True)).pack(
            fill="x", padx=14, pady=(0, 4))
        self.update_status_lbl = ctk.CTkLabel(c3, text="", font=_font(11),
                                              text_color=theme.MUTED, wraplength=460)
        self.update_status_lbl.pack(anchor="w", padx=14, pady=(0, 8))
        ctk.CTkFrame(c3, height=6, fg_color="transparent").pack()

    # ------------------------------------------------------------- setters

    def _set_mode(self, v: str) -> None:
        self.cfg.mode = v
        self.cfg.save()
        self._refresh_chips()

    def _set_suppress(self, v: int) -> None:
        self.cfg.suppress_hotkey = bool(v)
        self.cfg.save()
        self.apply_hotkey(self.cfg.hotkey)

    def _set_method(self, v: str) -> None:
        self.cfg.insertion_method = v
        self.cfg.save()

    def _set_input_device(self, label: str, devices: list[tuple[int, str]]) -> None:
        idx = next((i for i, name in devices if name == label), None)
        self.cfg.input_device_index = idx
        self.cfg.save()

    def _set_unload_idle(self, v: int) -> None:
        self.cfg.unload_model_idle_min = 15 if v else 0
        self.cfg.save()

    def _set_autostart(self, sw) -> None:
        err = autostart.set_enabled(bool(sw.get()))
        if err and not autostart.is_enabled():
            sw.deselect()

    def _set_model(self, v: str) -> None:
        self.cfg.model = v
        self.cfg.save()
        self.dictation.transcriber = Transcriber(self.cfg)
        self._refresh_chips()
        self.model_status.configure(text="Загрузится при следующей диктовке или по кнопке ниже.")

    def _set_lang(self, label: str) -> None:
        self.cfg.language = next(l[1] for l in LANGS if l[0] == label)
        self.cfg.save()

    def _set_threads(self, v: float) -> None:
        self.cfg.threads = int(round(v))
        self.cfg.save()
        self.thr_lbl.configure(text=f"Потоков CPU: {self.cfg.threads}")

    def _set_refine(self, v: int) -> None:
        self.cfg.refine_enabled = bool(v)
        self.cfg.save()

    def _preload_model(self) -> None:
        self.model_status.configure(text="Загрузка модели…")

        def work() -> None:
            try:
                self.dictation.transcriber.load()
                self.root.after(0, lambda: self.model_status.configure(text="Модель загружена ✓"))
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: self.model_status.configure(text=f"Ошибка: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------------------------------------- hotkey capture

    def _capture_hotkey(self) -> None:
        self.hk_btn.configure(text="Нажмите клавиши…")
        self.hk_err.configure(text="")
        mods: list[str] = []
        # Pause the global hotkey so its suppressed main key reaches us.
        if self.stop_hotkey is not None:
            self.stop_hotkey()

        def finish(spec: list[str] | None) -> None:
            self.settings_win.unbind("<KeyPress>", bid)
            if spec is None:
                self.apply_hotkey(self.cfg.hotkey)  # re-arm the old combo
                self.hk_btn.configure(text=describe(self.cfg.hotkey))
                return
            err = self.apply_hotkey(spec)
            if err:
                self.apply_hotkey(self.cfg.hotkey)
                self.hk_err.configure(text=err)
                self.hk_btn.configure(text=describe(self.cfg.hotkey))
            else:
                self.cfg.hotkey = spec
                self.cfg.save()
                self.hk_btn.configure(text=describe(spec))
                self._refresh_chips()

        def on_press(event) -> str:
            ks = event.keysym
            if ks in _MOD_KEYSYMS:
                if _MOD_KEYSYMS[ks] not in mods:
                    mods.append(_MOD_KEYSYMS[ks])
                return "break"
            if ks == "Escape":
                finish(None)
                return "break"
            main = self._keysym_to_token(ks)
            if main is None:
                return "break"
            finish(mods + [main])
            return "break"

        bid = self.settings_win.bind("<KeyPress>", on_press)
        self.settings_win.focus_force()

    @staticmethod
    def _keysym_to_token(ks: str) -> str | None:
        special = {"space": "space", "Return": "enter", "Tab": "tab"}
        if ks in special:
            return special[ks]
        if ks.startswith("F") and ks[1:].isdigit():
            return ks.lower()
        if len(ks) == 1 and ks.isprintable():
            return ks.lower()
        return None

    # ------------------------------------------------------- ollama helpers

    def _open_ollama_site(self) -> None:
        import webbrowser

        webbrowser.open("https://ollama.com/download")

    def _open_github(self) -> None:
        import webbrowser

        webbrowser.open("https://github.com/nowoandi/WinDictoo")

    def _copy_pull_cmd(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append("ollama pull qwen2.5:3b")
        self.root.update_idletasks()
        self._pull_btn.configure(text="Скопировано ✓  (вставьте в Терминал)")
        self.root.after(2500, lambda: self._pull_btn.configure(
            text="⧉ Скопировать команду модели"))

    # --------------------------------------------------------------- updates

    def check_update_async(self, force: bool = False) -> None:
        """Look up github.com/nowoandi/WinDictoo's latest release in the
        background. `force=True` (manual button in Settings) ignores a
        previously dismissed version; the automatic startup check does not,
        so the banner doesn't nag about the same release every launch."""
        from . import __version__

        def work() -> None:
            info = update.check_for_update(__version__)
            if info is None:
                if force:
                    self.root.after(0, lambda: self._set_update_status(
                        "Обновлений нет — установлена последняя версия."))
                return
            if not force and info.version == self.cfg.skipped_update_version:
                return
            try:
                self.root.after(0, lambda: self._show_update_banner(info))
            except RuntimeError:
                pass  # window already gone

        threading.Thread(target=work, daemon=True).start()

    def _set_update_status(self, text: str) -> None:
        if getattr(self, "update_status_lbl", None) is not None:
            try:
                self.update_status_lbl.configure(text=text)
            except tk.TclError:
                pass

    def _show_update_banner(self, info: update.UpdateInfo) -> None:
        self._update_info = info
        self._set_update_status(f"Доступна версия {info.version}.")
        if self._update_banner is not None:
            return
        banner = ctk.CTkButton(
            self.root, text=f"🔔  Доступна версия {info.version} — что нового",
            fg_color=theme.ACCENT_DIM, hover_color=theme.ACCENT_DIM, text_color=theme.TEXT,
            font=_font(12, "bold"), height=34, corner_radius=10,
            command=self._open_update_dialog,
        )
        banner.pack(fill="x", padx=20, pady=(0, 6), before=self.hero_frame)
        self._update_banner = banner

    def _hide_update_banner(self) -> None:
        if self._update_banner is not None:
            try:
                self._update_banner.destroy()
            except tk.TclError:
                pass
            self._update_banner = None

    def _open_update_dialog(self) -> None:
        info = self._update_info
        if info is None:
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Доступно обновление")
        win.geometry("480x420")
        win.configure(fg_color=theme.BG)
        win.transient(self.root)

        ctk.CTkLabel(win, text=f"WinDictoo {info.version}", font=_font(18, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(win, text="Что нового:", font=_font(12, "bold"),
                     text_color=theme.MUTED).pack(anchor="w", padx=20)
        box = ctk.CTkTextbox(win, font=_font(12), fg_color=theme.CARD,
                             text_color=theme.TEXT, corner_radius=12, wrap="word")
        box.pack(fill="both", expand=True, padx=20, pady=8)
        box.insert("1.0", info.notes or "(без описания)")
        box.configure(state="disabled")

        status = ctk.CTkLabel(win, text="", font=_font(11), text_color=theme.MUTED)
        status.pack(anchor="w", padx=20)

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(4, 20))

        def later() -> None:
            self.cfg.skipped_update_version = info.version
            self.cfg.save()
            self._hide_update_banner()
            try:
                win.destroy()
            except tk.TclError:
                pass

        def open_page() -> None:
            import webbrowser

            webbrowser.open(info.release_url)

        install_btn = ctk.CTkButton(btns, text="⬇ Скачать и установить", fg_color=theme.ACCENT,
                                    hover_color=theme.ACCENT_HOVER, font=_font(13, "bold"))
        install_btn.pack(side="right")
        ctk.CTkButton(btns, text="Страница релиза", fg_color=theme.CARD, hover_color=theme.CARD_HI,
                      text_color=theme.TEXT, command=open_page).pack(side="right", padx=8)
        ctk.CTkButton(btns, text="Позже", fg_color="transparent", hover_color=theme.CARD,
                      text_color=theme.MUTED, command=later).pack(side="left")

        def do_install() -> None:
            install_btn.configure(state="disabled", text="Скачиваю…")
            status.configure(text="")

            def work() -> None:
                import subprocess
                import tempfile
                from pathlib import Path

                try:
                    dest = Path(tempfile.gettempdir()) / f"WinDictoo-Setup-{info.version}.exe"
                    update.download_installer(info.download_url, str(dest))
                    subprocess.Popen([str(dest)], close_fds=True)  # noqa: S603
                except Exception as exc:  # noqa: BLE001
                    log.exception("update download/launch failed")

                    def fail() -> None:
                        install_btn.configure(state="normal", text="⬇ Скачать и установить")
                        status.configure(text=f"Не удалось: {exc}", text_color=theme.DANGER)

                    try:
                        self.root.after(0, fail)
                    except RuntimeError:
                        pass
                    return
                # The installer closes us via CloseApplications=yes; quitting
                # ourselves right away avoids racing that shutdown.
                try:
                    self.root.after(300, self.quit)
                except RuntimeError:
                    pass

            threading.Thread(target=work, daemon=True).start()

        install_btn.configure(command=do_install)

    # ---------------------------------------------------------------- helpers

    def preload_model_async(self) -> None:
        """Load the Whisper model in the background right after startup so the
        first dictation doesn't stall; the hero card shows what's happening."""
        if self.dictation.transcriber.is_loaded:
            return
        self.sub_lbl.configure(text="Загружаю модель распознавания…")

        def work() -> None:
            try:
                self.dictation.transcriber.load()
                msg = "Модель загружена ✓"
            except Exception as exc:  # noqa: BLE001
                log.exception("model preload failed")
                msg = f"Модель не загрузилась: {exc}"

            def done() -> None:
                try:
                    if self.dictation.state is State.IDLE and not self.dictation.message:
                        self.sub_lbl.configure(text=msg)
                        self.root.after(4000, self._clear_sub_if_idle)
                except tk.TclError:
                    pass

            try:
                self.root.after(0, done)
            except RuntimeError:
                pass  # window already gone

        threading.Thread(target=work, daemon=True).start()

    def _clear_sub_if_idle(self) -> None:
        try:
            if self.dictation.state is State.IDLE and not self.dictation.message:
                self.sub_lbl.configure(text="")
        except tk.TclError:
            pass

    def open_onboarding(self) -> None:
        from .onboarding import Onboarding

        Onboarding(self.root, self.cfg, self.dictation, self.apply_hotkey, on_finish=self.show,
                   stop_hotkey=self.stop_hotkey)

    def _open_log(self) -> None:
        import subprocess

        if LOG_PATH.exists():
            subprocess.Popen(["notepad.exe", str(LOG_PATH)])  # noqa: S603,S607

    def _open_config_dir(self) -> None:
        import subprocess

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(CONFIG_DIR)])  # noqa: S603,S607

    def hide_to_tray(self) -> None:
        self.root.withdraw()

    def show(self) -> None:
        # Reflect any change made while hidden (e.g. hotkey/model set in the
        # onboarding wizard or settings) — chips always show current config.
        self._refresh_chips()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit(self) -> None:
        self._closing = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self._on_quit()

    def run(self) -> None:
        self.root.mainloop()
