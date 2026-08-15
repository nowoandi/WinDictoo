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

from . import autostart, engine, i18n, insert as _insert, oldversions, refine, theme, update
from .app import Dictation, State
from .audio import input_devices
from .config import CONFIG_DIR, LOG_PATH, Config
from .hotkey import describe
from .transcribe import Transcriber
from .widgets import Equalizer, MicIndicator, aa_image

log = logging.getLogger(__name__)


def model_label(spec: engine.ModelSpec) -> str:
    """"Whisper small · 485 MB", "GigaAM v3 · 216 MB · RU".

    Model names are proper nouns and stay untranslated; only the size unit
    and the "many languages" tag go through i18n.
    """
    if spec.size_mb >= 1000:
        size = i18n.t("unit.gb", n=f"{spec.size_mb / 1000:.1f}".rstrip("0").rstrip("."))
    else:
        size = i18n.t("unit.mb", n=spec.size_mb)
    parts = [spec.title, size]
    if spec.langs is None:
        parts.append(i18n.t("rec.langs_all"))
    elif len(spec.langs) == 1:
        parts.append(spec.langs[0].upper())
    else:
        parts.append(i18n.t("rec.langs_count", n=len(spec.langs)))
    return " · ".join(parts)
# Native names, matching the existing "English"/"Deutsch" convention. All
# eight codes verified against faster_whisper.tokenizer._LANGUAGE_CODES.
LANGS = [
    ("Автоопределение", "auto"),
    ("Русский", "ru"),
    ("English", "en"),
    ("Deutsch", "de"),
    ("Français", "fr"),
    ("Español", "es"),
    ("中文", "zh"),
    ("Türkçe", "tr"),
    ("Հայերեն", "hy"),
]

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
        # Guards against several download-progress pumps ticking at once —
        # the model can be loaded from Settings, from startup and from a
        # dictation, and all three want to draw the same bar.
        self._model_pump_running = False

        theme.apply(cfg.ui_theme)
        i18n.set_language(cfg.ui_language)
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
        self._oldversions_banner: ctk.CTkButton | None = None
        self._oldversions_found: list[tuple[str, str, str]] = []
        self._theme_popup: tk.Toplevel | None = None
        self._lang_popup: tk.Toplevel | None = None
        self.settings_win: ctk.CTkToplevel | None = None
        self.overlay: tk.Toplevel | None = None
        self._ov_dot = None
        self._ov_dot_photo = None
        self._ov_label = None
        self._ov_msg = None
        self._ov_eq = None
        self._ov_stop = None
        self._ov_stop_photo = None

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
        # A little coloured square (this theme's accent) instead of a text
        # dropdown — clicking it drops down one square per theme, no labels.
        self.theme_swatch = ctk.CTkButton(
            header, text="", width=40, height=40, corner_radius=theme.RADIUS_WIDGET,
            border_width=1, border_color=theme.STROKE,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=lambda: self._open_theme_picker(self.theme_swatch),
        )
        self.theme_swatch.pack(side="right", padx=(0, 8))
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
        if self._oldversions_found:
            self._oldversions_banner = None
            self._show_oldversions_banner()
        self.mic = MicIndicator(hero, size=118, bg=theme.CARD)
        self.mic.pack(pady=(20, 4))
        self.mic.bind("<Button-1>", lambda e: self._toggle_dictation())
        self.mic.configure(cursor="hand2")
        self.status_lbl = ctk.CTkLabel(hero, text=i18n.state_label(State.IDLE),
                                       font=_font(17, "bold"), text_color=theme.TEXT)
        self.status_lbl.pack()
        self.eq = Equalizer(hero, width=250, height=38, bg=theme.CARD)
        self.eq.pack(pady=(4, 2))
        self.sub_lbl = ctk.CTkLabel(hero, text="", font=_font(11), text_color=theme.MUTED,
                                    wraplength=340)
        self.sub_lbl.pack(pady=(0, 16))

        # Chips row — hotkey + mode always; a third "Ollama" chip appears
        # only while refinement is enabled (nothing to show otherwise), so
        # this is rebuilt in place (not just re-labelled) whenever that
        # setting changes — see _build_chips/_set_refine.
        self.chips_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.chips_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._build_chips()

        # Primary Start/Stop button (label toggles with state).
        self.test_btn = ctk.CTkButton(self.root, text=i18n.t("main.btn_start"), height=48,
                                      corner_radius=theme.RADIUS_BUTTON, font=_font(15, "bold"),
                                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                      text_color=theme.ON_ACCENT,
                                      command=self._toggle_dictation)
        self.test_btn.pack(fill="x", padx=20, pady=(10, 4))

        # Result card (roomy, so the recognized text is always visible)
        self.result_card = ctk.CTkFrame(self.root, fg_color=theme.CARD,
                                        corner_radius=theme.RADIUS_CONTAINER,
                                        border_width=1, border_color=theme.STROKE)
        self.result_card.pack(fill="both", expand=True, padx=20, pady=(8, 18))
        rhead = ctk.CTkFrame(self.result_card, fg_color="transparent")
        rhead.pack(fill="x", padx=16, pady=(6, 2))
        ctk.CTkLabel(rhead, text=i18n.t("main.recognized_text_label"), font=_font(10, "bold"),
                     text_color=theme.MUTED).pack(side="left")
        # Accent-tinted label where that stays legible on CARD_HI, plain TEXT
        # where it doesn't (the dark palette's accent measured only 2.40:1).
        chip_text = theme.readable_on(theme.CARD_HI, theme.ACCENT_HOVER, theme.ACCENT, theme.TEXT)
        self.copy_btn = ctk.CTkButton(rhead, text=i18n.t("common.copy"), width=110, height=28,
                                      corner_radius=theme.RADIUS_WIDGET, font=_font(11, "bold"),
                                      fg_color=theme.CARD_HI, hover_color=theme.STROKE,
                                      text_color=chip_text, border_width=1,
                                      border_color=theme.STROKE, command=self._copy_result)
        self.copy_btn.pack(side="right")
        # Quick recognition-language switch, right next to Copy — dictation
        # language is changed often enough (mid-session, multilingual users)
        # that burying it in Settings -> Распознавание was too many clicks.
        # Shows the current speech language as a short international code
        # (EN/DE/FR/RU/...) so the button itself reflects the active choice.
        self.lang_btn = ctk.CTkButton(rhead, text=self._lang_abbr(self.cfg.language), width=40, height=28,
                                      corner_radius=theme.RADIUS_WIDGET, font=_font(11, "bold"),
                                      fg_color=theme.CARD_HI, hover_color=theme.STROKE,
                                      text_color=chip_text, border_width=1,
                                      border_color=theme.STROKE,
                                      command=lambda: self._open_lang_picker(self.lang_btn))
        self.lang_btn.pack(side="right", padx=(0, 8))
        # Editable: recognition isn't perfect, so letting the user fix a
        # word or two before copying/reinserting beats forcing a redo of the
        # whole dictation. undo=True gives Ctrl+Z a real edit to undo.
        self.result_box = ctk.CTkTextbox(self.result_card, font=_font(13), fg_color=theme.CARD_HI,
                                         text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                                         wrap="word", border_width=1, border_color=theme.STROKE,
                                         height=80, undo=True)
        self.result_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.result_box.bind("<FocusIn>", self._result_focus_in)
        self.result_box.bind("<FocusOut>", self._result_focus_out)
        self._show_placeholder()

    def _chip(self, parent, text: str, expand: bool = False, last: bool = False) -> ctk.CTkLabel:
        f = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=theme.RADIUS_CHIP,
                         border_width=1, border_color=theme.STROKE)
        # fill="x" + expand=True: each chip actually stretches to its equal
        # half of the row instead of staying pill-sized with empty space
        # around it — combined width matches the Старт button below (no
        # trailing gap after the last chip, so the row's right edge lines
        # up with the button's).
        f.pack(side="left", padx=(0, 0 if last else 8), expand=expand,
              fill="x" if expand else "none")
        lbl = ctk.CTkLabel(f, text=text, font=_font(11), text_color=theme.MUTED)
        lbl.pack(padx=12, pady=6)
        return lbl

    def _refresh_chips(self) -> None:
        self.hotkey_chip.configure(text="⌨  " + describe(self.cfg.hotkey))
        self.mode_chip.configure(text="⏱  " + (i18n.t("main.mode_hold_short") if self.cfg.mode == "hold"
                                                else i18n.t("main.mode_toggle_long")))
        self.root.update_idletasks()

    def _build_chips(self) -> None:
        """(Re)build the chip row in place — called at startup and again
        whenever refinement is toggled, since a chip only exists while
        there's something to report (unlike hotkey/mode, always present)."""
        for w in list(self.chips_frame.winfo_children()):
            w.destroy()
        show_refine = self.cfg.refine_enabled
        self.hotkey_chip = self._chip(self.chips_frame, "⌨ " + describe(self.cfg.hotkey), expand=True)
        self.mode_chip = self._chip(
            self.chips_frame, "⏱ " + (i18n.t("main.mode_hold_short") if self.cfg.mode == "hold"
                                      else i18n.t("main.mode_toggle_short")),
            expand=True, last=not show_refine)
        if show_refine:
            self.refine_chip = self._chip(self.chips_frame, i18n.t("main.refine_checking"),
                                          expand=True, last=True)
            self._refresh_refine_status()
        else:
            self.refine_chip = None

    def _refresh_refine_status(self) -> None:
        """Pings Ollama in the background and updates the chip; reschedules
        itself every 30s so the indicator reflects Ollama actually being up,
        not just the setting being on. Stops cleanly once refinement is
        turned off or the chip/window is gone (never leaks after a rebuild:
        it always re-reads self.refine_chip rather than closing over it)."""
        if not self.cfg.refine_enabled or self.refine_chip is None:
            return

        def work() -> None:
            try:
                ok = bool(refine.list_models(self.cfg.ollama_endpoint))
            except Exception:  # noqa: BLE001
                ok = False

            def apply() -> None:
                if self.refine_chip is None:
                    return
                try:
                    self.refine_chip.configure(
                        text=i18n.t("main.refine_connected" if ok else "main.refine_disconnected"))
                except tk.TclError:
                    pass

            try:
                self.root.after(0, apply)
            except RuntimeError:
                pass

        threading.Thread(target=work, daemon=True).start()
        try:
            self.root.after(30000, self._refresh_refine_status)
        except RuntimeError:
            pass

    # ------------------------------------------------------------ state/render

    def _on_state(self, state: State) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._render(state))
        except RuntimeError:
            pass  # mainloop already stopped (shutdown race)

    def _render(self, state: State) -> None:
        label = i18n.state_label(state)
        # The first transcription silently pays the model-load cost, which
        # looks like a hang — name what is actually happening.
        loading_model = (
            state is State.TRANSCRIBING and not self.dictation.transcriber.is_loaded
        )
        if loading_model:
            label = i18n.t("main.state_loading_model")
        self.status_lbl.configure(text=label,
                                  text_color=theme.STATE_COLOR.get(state, theme.TEXT))
        self.mic.set_state(state)
        self.sub_lbl.configure(text=self.dictation.message or self._default_sub(state))
        self.eq.set_active(state is State.RECORDING)
        # Button reflects what a click will do next.
        if state is State.RECORDING:
            self.test_btn.configure(text=i18n.t("main.btn_stop"), fg_color=theme.DANGER, hover_color="#e03e5c")
        elif state is State.IDLE:
            self.test_btn.configure(text=i18n.t("main.btn_start"), fg_color=theme.ACCENT,
                                    hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT)
        else:
            self.test_btn.configure(text="…   " + i18n.state_label(state),
                                    fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                    text_color=theme.ON_ACCENT)
        if state is State.RECORDING:
            self._pump_level()
        # After sub_lbl above, not before: the pump writes the download figure
        # into that same label and must not be overwritten by this render.
        if loading_model:
            self._pump_model_progress()
        self._render_overlay(state)

    def _default_sub(self, state: State) -> str:
        if state in (State.RECORDING, State.TRANSCRIBING, State.REFINING):
            return i18n.t("main.esc_cancel")
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

    # ------------------------------------------------------ result placeholder
    #
    # The hint text ("Нажмите Старт…") lives in the same editable box as the
    # real transcript, so it must never be mistaken for content. Two rules
    # keep that airtight:
    #
    #  1. `_result_is_placeholder` is the ONLY source of truth — never infer
    #     it by comparing the box text against the hint string (that breaks
    #     the moment someone dictates the hint's exact wording).
    #  2. Every transition calls edit_reset(). The box has undo=True, so
    #     without it the placeholder's deletion sits on the undo stack and a
    #     later Ctrl+Z can splice the hint straight back into a finished
    #     transcript — which is exactly the failure mode to avoid here.

    def _show_placeholder(self) -> None:
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", i18n.t("main.result_placeholder"))
        self.result_box.configure(text_color=theme.MUTED)
        self._result_is_placeholder = True
        self.result_box.edit_reset()

    def _clear_placeholder(self) -> None:
        if not getattr(self, "_result_is_placeholder", False):
            return
        self.result_box.delete("1.0", "end")
        self.result_box.configure(text_color=theme.TEXT)
        self._result_is_placeholder = False
        self.result_box.edit_reset()

    def _result_focus_in(self, _event=None) -> None:
        self._clear_placeholder()

    def _result_focus_out(self, _event=None) -> None:
        # Only ever restore into a genuinely empty box — never overwrite a
        # transcript the user is still working on.
        try:
            if not self._result_is_placeholder and not self.result_box.get("1.0", "end").strip():
                self._show_placeholder()
        except tk.TclError:
            pass  # widget already destroyed (theme/language rebuild)

    def _show_result(self, text: str) -> None:
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text or i18n.t("main.result_empty"))
        self.result_box.configure(text_color=theme.TEXT)
        self._result_is_placeholder = False
        self.result_box.edit_reset()  # a fresh dictation isn't an "undo" of the last edit

    def _copy_result(self) -> None:
        if getattr(self, "_result_is_placeholder", False):
            return  # the hint is not content — nothing to copy
        text = self.result_box.get("1.0", "end").strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.copy_btn.configure(text=i18n.t("common.copied"))
        self.root.after(1500, lambda: self.copy_btn.configure(text=i18n.t("common.copy")))

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
        self._ov_dot_photo = aa_image(24, 24, theme.CARD,
                                      lambda d, k, col=col: d.ellipse([3 * k, 3 * k, 21 * k, 21 * k], fill=col))
        self._ov_dot.create_image(0, 0, anchor="nw", image=self._ov_dot_photo)
        self._ov_label.configure(text=i18n.state_label(state))
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
            glyph, gx, gy, gfont = "■", 20, 20, ("Segoe UI", 13)
        else:
            col = theme.SUCCESS
            glyph, gx, gy, gfont = "✓", 21, 19, ("Segoe UI", 16, "bold")
        self._ov_stop_photo = aa_image(40, 40, theme.CARD,
                                       lambda d, k, col=col: d.ellipse([3 * k, 3 * k, 37 * k, 37 * k], fill=col))
        c.create_image(0, 0, anchor="nw", image=self._ov_stop_photo)
        c.create_text(gx, gy, text=glyph, fill=theme.ON_ACCENT, font=gfont)

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

    def _open_theme_picker(self, anchor: ctk.CTkButton) -> None:
        """A borderless popup of plain colour squares (each theme's ACCENT,
        no text) directly under `anchor` — reopening on the other swatch
        (header vs. Settings) or clicking the same one again just replaces
        it rather than stacking popups."""
        self._close_theme_popup()
        popup = tk.Toplevel(anchor)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=theme.STROKE)
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        popup.geometry(f"+{x}+{y}")

        inner = tk.Frame(popup, bg=theme.CARD)
        inner.pack(padx=1, pady=1)  # 1px border effect via the bg peeking through
        for key in theme.THEME_LABELS:
            color = theme.PALETTES[key]["ACCENT"]
            sw = tk.Canvas(inner, width=32, height=32, bg=theme.CARD,
                           highlightthickness=0, cursor="hand2")
            box = sw.create_rectangle(4, 4, 28, 28, fill=color, outline=theme.STROKE)
            if key == self.cfg.ui_theme:
                sw.create_rectangle(1, 1, 31, 31, outline=color, width=2)
            sw.bind("<Button-1>", lambda _e, k=key: self._pick_theme_from_swatch(k))
            sw.pack(padx=6, pady=6)

        self._theme_popup = popup
        popup.bind("<FocusOut>", lambda _e: self._close_theme_popup())
        popup.focus_force()

    def _pick_theme_from_swatch(self, key: str) -> None:
        self._close_theme_popup()
        self.set_theme(key)

    def _close_theme_popup(self) -> None:
        popup = getattr(self, "_theme_popup", None)
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
            self._theme_popup = None

    # ------------------------------------------------------ language quick-pick

    def _open_lang_picker(self, anchor: ctk.CTkButton) -> None:
        """Borderless popup listing every recognition language (native name),
        so switching the language Whisper listens for doesn't require a trip
        into Settings -> Распознавание. Purely Config.language — independent
        of the interface language (Config.ui_language, set in Settings)."""
        self._close_lang_popup()
        popup = tk.Toplevel(anchor)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=theme.STROKE)
        x = anchor.winfo_rootx() + anchor.winfo_width() - 150
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        popup.geometry(f"+{max(x, 0)}+{y}")

        inner = tk.Frame(popup, bg=theme.CARD)
        inner.pack(padx=1, pady=1)
        for label, code in LANGS:
            row = tk.Label(inner, text=label, font=("Segoe UI", 12), anchor="w",
                           bg=theme.ACCENT_DIM if code == self.cfg.language else theme.CARD,
                           fg=theme.TEXT, cursor="hand2", padx=14, pady=6, width=16)
            row.pack(fill="x")
            row.bind("<Button-1>", lambda _e, c=code: self._pick_lang_from_popup(c))
            row.bind("<Enter>", lambda _e, w=row: w.configure(bg=theme.STROKE))
            row.bind("<Leave>", lambda _e, w=row, c=code: w.configure(
                bg=theme.ACCENT_DIM if c == self.cfg.language else theme.CARD))

        self._lang_popup = popup
        popup.bind("<FocusOut>", lambda _e: self._close_lang_popup())
        popup.focus_force()

    @staticmethod
    def _lang_abbr(code: str) -> str:
        """Short international code shown on the quick-switch button itself
        (EN/DE/FR/RU/...) — every LANGS code is already ISO 639-1 except the
        special "auto" entry."""
        return "AUTO" if code == "auto" else code.upper()

    def _pick_lang_from_popup(self, code: str) -> None:
        self._close_lang_popup()
        self.cfg.language = code
        self.cfg.save()
        self.lang_btn.configure(text=self._lang_abbr(code))
        var = getattr(self, "_lang_option_var", None)
        if var is not None and self.settings_win is not None:
            label = next((l for l, c in LANGS if c == code), None)
            if label is not None:
                try:
                    var.set(label)
                except tk.TclError:
                    pass

    def _close_lang_popup(self) -> None:
        popup = getattr(self, "_lang_popup", None)
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
            self._lang_popup = None

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
        self.root.after(140, self._rebuild_ui)

    def _set_ui_language(self, label: str) -> None:
        code = next((c for l, c in i18n.UI_LANGS if l == label), None)
        if code is None or code == self.cfg.ui_language:
            return
        self.cfg.ui_language = code
        self.cfg.save()
        i18n.set_language(code)
        try:
            self.root.focus_set()
        except tk.TclError:
            pass
        self.root.after(140, self._rebuild_ui)

    @staticmethod
    def _recolor_segmented(seg: ctk.CTkSegmentedButton, selected: str) -> None:
        """CTkSegmentedButton (and CTkTabview, which is built on one) exposes
        a single `text_color` shared by selected and unselected segments. The
        selected one is filled with ACCENT, so it inherits a colour chosen for
        the unselected background — on a bright accent that's unreadable
        (neon green measured 1.06:1, i.e. no contrast at all). Recolour each
        internal button by hand: ON_ACCENT on the filled one, TEXT on the rest.

        Must be called again on every switch — CTk repaints the fills itself
        but never touches these per-button text colours."""
        for value, btn in seg._buttons_dict.items():
            try:
                btn.configure(text_color=theme.ON_ACCENT if value == selected else theme.TEXT)
            except (tk.TclError, AttributeError):
                pass

    def _segmented(self, parent, values: list[str], current: str, on_change) -> ctk.CTkSegmentedButton:
        """A themed segmented button. Without the explicit colours below CTk
        falls back to its own built-in palette (a light grey fill and #dce4ee
        text) that ignores the active theme entirely."""
        seg = ctk.CTkSegmentedButton(
            parent, values=values,
            corner_radius=theme.RADIUS_WIDGET,
            fg_color=theme.STROKE,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.CARD, unselected_hover_color=theme.CARD_HI,
            text_color=theme.TEXT,
            command=lambda v: (on_change(v), self._recolor_segmented(seg, v)))
        seg.set(current)
        self._recolor_segmented(seg, current)
        return seg

    def _rebuild_ui(self) -> None:
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
        self._show_result(i18n.t("state.recording"))

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
        win.title(i18n.t("main.settings_title"))
        win.geometry("560x720")
        win.configure(fg_color=theme.BG)
        win.transient(self.root)
        self.settings_win = win
        # See _recolor_segmented: a CTkTabview is a CTkSegmentedButton under
        # the hood and shares its single-text_color limitation.
        def _recolor_tabs() -> None:
            self._recolor_segmented(tabs._segmented_button, tabs.get())

        tabs = ctk.CTkTabview(win, fg_color=theme.CARD, segmented_button_fg_color=theme.CARD,
                              segmented_button_selected_color=theme.ACCENT,
                              segmented_button_selected_hover_color=theme.ACCENT_HOVER,
                              segmented_button_unselected_color=theme.CARD,
                              segmented_button_unselected_hover_color=theme.CARD_HI,
                              text_color=theme.TEXT,
                              corner_radius=theme.RADIUS_CARD,
                              border_width=1, border_color=theme.STROKE,
                              command=_recolor_tabs)
        tabs.pack(fill="both", expand=True, padx=16, pady=16)
        t_general, t_recognition = i18n.t("tabs.general"), i18n.t("tabs.recognition")
        t_refinement, t_privacy = i18n.t("tabs.refinement"), i18n.t("tabs.privacy")
        for name in (t_general, t_recognition, t_refinement, t_privacy):
            tabs.add(name)
        self._tab_general(tabs.tab(t_general))
        self._tab_transcription(tabs.tab(t_recognition))
        self._tab_refinement(tabs.tab(t_refinement))
        self._tab_privacy(tabs.tab(t_privacy))
        _recolor_tabs()

        # Fit the height to the tallest tab, capped to the monitor's work
        # area: a fixed 720 clipped the bottom of the General tab once it
        # grew to six cards, silently hiding the autostart switch.
        win.update_idletasks()
        try:
            import ctypes

            scale = ctk.ScalingTracker.get_window_scaling(win)
            tallest = max(
                tabs.tab(n).winfo_reqheight()
                for n in (t_general, t_recognition, t_refinement, t_privacy)
            )

            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            work = _RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
            need = int(tallest / scale) + 162  # + tab bar and paddings
            cap = int((work.bottom - work.top - 60) / scale)
            win.geometry(f"560x{max(600, min(need, cap))}")
        except Exception:  # noqa: BLE001 - sizing must never break Settings
            win.geometry("560x760")
        win.minsize(520, 520)

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=theme.CARD_HI, corner_radius=theme.RADIUS_CARD,
                             border_width=1, border_color=theme.STROKE)
        outer.pack(fill="x", padx=6, pady=7)
        ctk.CTkLabel(outer, text=title.upper(), font=_font(10, "bold"),
                     text_color=theme.MUTED).pack(anchor="w", padx=14, pady=(10, 2))
        return outer

    def _tab_general(self, tab) -> None:
        c1 = self._card(tab, i18n.t("gen.card_hotkey"))
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(row, text=i18n.t("gen.hotkey_label"), font=_font(13), text_color=theme.TEXT).pack(side="left")
        self.hk_btn = ctk.CTkButton(row, text=describe(self.cfg.hotkey), width=170,
                                    corner_radius=theme.RADIUS_BUTTON,
                                    fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                    text_color=theme.ON_ACCENT,
                                    command=self._capture_hotkey)
        self.hk_btn.pack(side="right")
        self.hk_err = ctk.CTkLabel(c1, text="", font=_font(11), text_color=theme.DANGER)
        self.hk_err.pack(anchor="w", padx=14)
        mode_hold, mode_toggle = i18n.t("gen.mode_hold"), i18n.t("gen.mode_toggle")
        mode = self._segmented(
            c1, [mode_hold, mode_toggle],
            mode_hold if self.cfg.mode == "hold" else mode_toggle,
            lambda v: self._set_mode("hold" if v == mode_hold else "toggle"))
        mode.pack(fill="x", padx=14, pady=(2, 12))
        sup = ctk.CTkSwitch(c1, text=i18n.t("gen.suppress_switch"),
                            font=_font(12), progress_color=theme.ACCENT,
                            command=lambda: self._set_suppress(sup.get()))
        sup.select() if self.cfg.suppress_hotkey else sup.deselect()
        sup.pack(anchor="w", padx=14, pady=(0, 12))

        c2 = self._card(tab, i18n.t("gen.card_insertion"))
        insertion_type, insertion_paste = i18n.t("gen.insertion_type"), i18n.t("gen.insertion_paste")
        method = self._segmented(
            c2, [insertion_type, insertion_paste],
            insertion_type if self.cfg.insertion_method == "type" else insertion_paste,
            lambda v: self._set_method("type" if v == insertion_type else "paste"))
        method.pack(fill="x", padx=14, pady=(2, 12))

        c_mic = self._card(tab, i18n.t("gen.card_mic"))
        devices = input_devices()
        mic_default = i18n.t("gen.mic_default")
        mic_labels = [mic_default] + [name for _, name in devices]
        current_label = next(
            (name for idx, name in devices if idx == self.cfg.input_device_index),
            mic_default,
        )
        mic_var = ctk.StringVar(value=current_label)
        ctk.CTkOptionMenu(c_mic, values=mic_labels, variable=mic_var, fg_color=theme.CARD,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          command=lambda v: self._set_input_device(v, devices)).pack(
            fill="x", padx=14, pady=(2, 6))
        ctk.CTkLabel(c_mic, text=i18n.t("gen.mic_hint"),
                     font=_font(11), text_color=theme.MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 10))

        # How long the capture stream is held open. Opening a device costs
        # 100-400 ms, which used to eat the first syllable of every dictation.
        ctk.CTkLabel(c_mic, text=i18n.t("gen.mic_mode_label"), font=_font(12),
                     text_color=theme.TEXT).pack(anchor="w", padx=14)
        mic_modes = [
            (i18n.t("gen.mic_mode_lazy"), "lazy"),
            (i18n.t("gen.mic_mode_always"), "always"),
            (i18n.t("gen.mic_mode_on_demand"), "on_demand"),
        ]
        current_mode = next(
            (lbl for lbl, val in mic_modes if val == self.cfg.mic_mode), mic_modes[0][0]
        )
        self._segmented(
            c_mic, [lbl for lbl, _ in mic_modes], current_mode,
            lambda v: self._set_mic_mode(next(m for lbl, m in mic_modes if lbl == v)),
        ).pack(fill="x", padx=14, pady=(2, 4))
        self._mic_mode_hint = ctk.CTkLabel(
            c_mic, text=i18n.t(f"gen.mic_mode_hint_{self.cfg.mic_mode}"),
            font=_font(11), text_color=theme.MUTED, wraplength=460, justify="left")
        self._mic_mode_hint.pack(anchor="w", padx=14, pady=(0, 12))

        # Theme swatch and UI language share one row: six stacked cards no
        # longer fit the window and pushed the autostart card out of view.
        c_look = self._card(tab, i18n.t("gen.card_appearance"))
        look = ctk.CTkFrame(c_look, fg_color="transparent")
        look.pack(fill="x", padx=14, pady=(2, 12))
        settings_swatch = ctk.CTkButton(
            look, text="", width=40, height=28, corner_radius=theme.RADIUS_WIDGET,
            border_width=1, border_color=theme.STROKE,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        )
        settings_swatch.configure(command=lambda: self._open_theme_picker(settings_swatch))
        settings_swatch.pack(side="left")
        uv = ctk.StringVar(value=next(l[0] for l in i18n.UI_LANGS if l[1] == self.cfg.ui_language))
        ctk.CTkOptionMenu(look, values=[l[0] for l in i18n.UI_LANGS], variable=uv, fg_color=theme.CARD,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          command=lambda v: self._set_ui_language(v)).pack(
            side="left", fill="x", expand=True, padx=(12, 0))

        c3 = self._card(tab, i18n.t("gen.card_app"))
        auto = ctk.CTkSwitch(c3, text=i18n.t("gen.autostart_switch"), font=_font(12),
                             progress_color=theme.ACCENT)
        auto.select() if autostart.is_enabled() else auto.deselect()
        auto.configure(command=lambda: self._set_autostart(auto))
        auto.pack(anchor="w", padx=14, pady=(2, 12))

    def _tab_transcription(self, tab) -> None:
        c1 = self._card(tab, i18n.t("rec.card_model"))
        self._model_ids = {model_label(m): m.id for m in engine.MODELS}
        current = engine.spec(self.cfg.model)
        mv = ctk.StringVar(value=model_label(current))
        # text_color must be explicit: CTk's default button text is white,
        # which vanishes on the white CARD background of the light theme.
        om = ctk.CTkOptionMenu(c1, values=list(self._model_ids), variable=mv, fg_color=theme.CARD,
                               text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                               button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                               command=lambda v: self._set_model(v))
        om.pack(fill="x", padx=14, pady=(2, 6))
        self.model_status = ctk.CTkLabel(c1, text=self._model_hint(current),
                                         font=_font(11), text_color=theme.MUTED, wraplength=460,
                                         justify="left")
        self.model_status.pack(anchor="w", padx=14)
        # Packed only while a download is running (see _show_model_bar): a
        # first run pulls 216 MB to 3 GB, and an app that just sits silent for
        # minutes reads as broken.
        self.model_bar = ctk.CTkProgressBar(c1, progress_color=theme.ACCENT,
                                            corner_radius=theme.RADIUS_WIDGET)
        self.model_bar.set(0)
        ctk.CTkButton(c1, text=i18n.t("rec.btn_load_now"), corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ON_ACCENT,
                      command=self._start_model_load).pack(anchor="w", padx=14, pady=10)

        c2 = self._card(tab, i18n.t("rec.card_params"))
        lv = ctk.StringVar(value=next(l[0] for l in LANGS if l[1] == self.cfg.language))
        self._lang_option_var = lv
        ctk.CTkLabel(c2, text=i18n.t("rec.lang_label"), font=_font(12), text_color=theme.TEXT).pack(anchor="w", padx=14)
        ctk.CTkOptionMenu(c2, values=[l[0] for l in LANGS], variable=lv, fg_color=theme.CARD,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          command=lambda v: self._set_lang(v)).pack(fill="x", padx=14, pady=(2, 2))
        self._lang_note = ctk.CTkLabel(c2, text=self._model_hint(engine.spec(self.cfg.model)),
                                       font=_font(11), text_color=theme.MUTED, wraplength=460,
                                       justify="left")
        self._lang_note.pack(anchor="w", padx=14, pady=(0, 8))
        self.thr_lbl = ctk.CTkLabel(c2, text=i18n.t("rec.threads_label", n=self.cfg.threads), font=_font(12),
                                    text_color=theme.TEXT)
        self.thr_lbl.pack(anchor="w", padx=14)
        sl = ctk.CTkSlider(c2, from_=1, to=16, number_of_steps=15, progress_color=theme.ACCENT,
                           button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                           command=self._set_threads)
        sl.set(self.cfg.threads)
        sl.pack(fill="x", padx=14, pady=(2, 12))

        c3 = self._card(tab, i18n.t("rec.card_memory"))
        unload = ctk.CTkSwitch(
            c3, text=i18n.t("rec.unload_switch"), font=_font(12),
            progress_color=theme.ACCENT,
            command=lambda: self._set_unload_idle(unload.get()))
        unload.select() if self.cfg.unload_model_idle_min else unload.deselect()
        unload.pack(anchor="w", padx=14, pady=(2, 4))
        ctk.CTkLabel(c3, text=i18n.t("rec.unload_hint"),
                     font=_font(11), text_color=theme.MUTED, wraplength=460,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 12))

    def _tab_refinement(self, tab) -> None:
        c0 = self._card(tab, i18n.t("ref.card_what"))
        ctk.CTkLabel(
            c0, text=i18n.t("ref.what_text"),
            font=_font(12), text_color=theme.TEXT, wraplength=470, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        cs = self._card(tab, i18n.t("ref.card_howto"))
        for key in ["ref.step1", "ref.step2", "ref.step3", "ref.step4", "ref.step5"]:
            ctk.CTkLabel(cs, text=i18n.t(key), font=_font(12), text_color=theme.TEXT,
                         wraplength=470, justify="left").pack(anchor="w", padx=14, pady=1)
        btns = ctk.CTkFrame(cs, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(8, 12))
        ctk.CTkButton(btns, text=i18n.t("ref.btn_ollama_site"), corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ON_ACCENT,
                      command=self._open_ollama_site).pack(side="left")
        self._pull_btn = ctk.CTkButton(btns, text=i18n.t("ref.btn_copy_pull"),
                                       corner_radius=theme.RADIUS_BUTTON,
                                       fg_color=theme.CARD, hover_color=theme.CARD_HI,
                                       text_color=theme.TEXT, border_width=1,
                                       border_color=theme.STROKE,
                                       command=self._copy_pull_cmd)
        self._pull_btn.pack(side="left", padx=8)

        c1 = self._card(tab, i18n.t("ref.card_settings"))
        en = ctk.CTkSwitch(c1, text=i18n.t("ref.enable_switch"), font=_font(12),
                           progress_color=theme.ACCENT, command=lambda: self._set_refine(en.get()))
        en.select() if self.cfg.refine_enabled else en.deselect()
        en.pack(anchor="w", padx=14, pady=(2, 8))
        ep = ctk.CTkEntry(c1, placeholder_text="http://127.0.0.1:11434", fg_color=theme.CARD,
                          corner_radius=theme.RADIUS_WIDGET, border_width=1, border_color=theme.STROKE)
        ep.insert(0, self.cfg.ollama_endpoint)
        ep.pack(fill="x", padx=14, pady=4)
        self.ollama_model = ctk.CTkEntry(c1, placeholder_text=i18n.t("ref.model_placeholder"),
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
            self.ollama_status.configure(text=i18n.t("ref.checking"))

            def work() -> None:
                local: list[str] = []
                try:
                    names = refine.list_models(ep.get())
                    # Ollama lists its cloud-routed models alongside the local
                    # ones. They are refused at dictation time (refine.refine),
                    # so keep them out of the "available" list and say why.
                    local = [n for n in names if not refine.is_cloud_model(n)]
                    cloud = [n for n in names if refine.is_cloud_model(n)]
                    msg = i18n.t("ref.available", names=", ".join(local)) if local else \
                        i18n.t("ref.no_models")
                    if cloud:
                        msg += "\n" + i18n.t("ref.cloud_in_list", names=", ".join(cloud))
                except refine.NonLocalEndpoint:
                    msg = i18n.t("ref.non_local")
                except Exception as exc:  # noqa: BLE001
                    msg = i18n.t("ref.not_running", error=exc)

                def apply() -> None:
                    chosen = self.ollama_model.get().strip()
                    if chosen and refine.is_cloud_model(chosen):
                        # Whatever else the check found, this is the thing the
                        # user needs to read.
                        self.ollama_status.configure(
                            text=i18n.t("ref.cloud_blocked", name=chosen))
                        return
                    self.ollama_status.configure(text=msg)
                    # Convenience: fill the model field with the first found
                    # model so a novice doesn't have to type it by hand — a
                    # local one, never a cloud model.
                    if local and not chosen:
                        self.ollama_model.insert(0, local[0])
                        self.cfg.ollama_model = local[0]
                        self.cfg.save()

                self.root.after(0, apply)

            threading.Thread(target=work, daemon=True).start()

        ctk.CTkButton(c1, text=i18n.t("ref.btn_check"), corner_radius=theme.RADIUS_BUTTON,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ON_ACCENT,
                      command=check).pack(anchor="w", padx=14, pady=10)

    def _tab_privacy(self, tab) -> None:
        c1 = self._card(tab, i18n.t("priv.card_data"))
        for key in ["priv.p1", "priv.p2", "priv.p3", "priv.p4", "priv.p5"]:
            ctk.CTkLabel(c1, text="✓  " + i18n.t(key), font=_font(12), text_color=theme.TEXT,
                         wraplength=470, justify="left").pack(anchor="w", padx=14, pady=2)
        ctk.CTkFrame(c1, height=6, fg_color="transparent").pack()

        c2 = self._card(tab, i18n.t("priv.card_diagnostics"))
        for key, cmd in [
            ("priv.btn_show_onboarding", self.open_onboarding),
            ("priv.btn_open_log", self._open_log),
            ("priv.btn_open_config", self._open_config_dir),
        ]:
            ctk.CTkButton(c2, text=i18n.t(key), fg_color=theme.CARD, hover_color=theme.CARD_HI,
                          text_color=theme.TEXT, corner_radius=theme.RADIUS_BUTTON,
                          border_width=1, border_color=theme.STROKE,
                          anchor="w", command=cmd).pack(fill="x", padx=14, pady=4)
        ctk.CTkFrame(c2, height=6, fg_color="transparent").pack()

        c3 = self._card(tab, i18n.t("priv.card_about"))
        from . import __version__

        ctk.CTkLabel(c3, text=f"WinDictoo {__version__}", font=_font(13, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=14, pady=(0, 2))
        ctk.CTkLabel(c3, text=i18n.t("priv.about_license"),
                     font=_font(12), text_color=theme.TEXT, wraplength=470,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        ctk.CTkButton(c3, text=i18n.t("priv.btn_github"), fg_color=theme.CARD,
                      hover_color=theme.CARD_HI, text_color=theme.TEXT,
                      corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=theme.STROKE,
                      anchor="w", command=self._open_github).pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkButton(c3, text=i18n.t("priv.btn_check_updates"), fg_color=theme.CARD,
                      hover_color=theme.CARD_HI, text_color=theme.TEXT,
                      corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=theme.STROKE,
                      anchor="w",
                      command=lambda: self.check_update_async(force=True)).pack(
            fill="x", padx=14, pady=(0, 4))
        ctk.CTkButton(c3, text=i18n.t("priv.btn_eventkauf"), fg_color=theme.CARD,
                      hover_color=theme.CARD_HI, text_color=theme.TEXT,
                      corner_radius=theme.RADIUS_BUTTON, border_width=1, border_color=theme.STROKE,
                      anchor="w", command=self._open_eventkauf).pack(fill="x", padx=14, pady=(0, 4))
        # Usually empty (only filled in by an update check) — kept last so
        # its reserved line height doesn't wedge a gap between unrelated
        # buttons above it.
        self.update_status_lbl = ctk.CTkLabel(c3, text="", font=_font(11),
                                              text_color=theme.MUTED, wraplength=460)
        self.update_status_lbl.pack(anchor="w", padx=14, pady=(0, 4))
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
        # The stream is now long-lived, so a device change has to close the
        # old one; otherwise the app keeps listening to the previous
        # microphone until the next idle timeout.
        self.dictation.recorder.release()
        self.dictation.warm_up()

    def _set_mic_mode(self, mode: str) -> None:
        self.cfg.mic_mode = mode
        self.cfg.save()
        self._mic_mode_hint.configure(text=i18n.t(f"gen.mic_mode_hint_{mode}"))
        if mode == "always":
            self.dictation.warm_up()
        else:
            # Drop it now rather than at some later timeout, so switching away
            # from "always" visibly clears the microphone-in-use indicator.
            self.dictation.recorder.release()

    def _set_unload_idle(self, v: int) -> None:
        self.cfg.unload_model_idle_min = 15 if v else 0
        self.cfg.save()

    def _set_autostart(self, sw) -> None:
        err = autostart.set_enabled(bool(sw.get()))
        if err and not autostart.is_enabled():
            sw.deselect()

    def _model_hint(self, spec: engine.ModelSpec) -> str:
        """One line under the picker saying what this model does about
        language — the setting below is meaningless for GigaAM and Parakeet,
        and silently ignoring it would be baffling."""
        if spec.honors_language:
            return i18n.t("rec.model_hint")
        fixed = spec.fixed_language
        if fixed is not None:
            name = next((l[0] for l in LANGS if l[1] == fixed), fixed.upper())
            return i18n.t("rec.model_fixed_language", language=name)
        return i18n.t("rec.model_detects_language")

    def _set_model(self, label: str) -> None:
        spec = engine.spec(self._model_ids[label])
        self.cfg.model = spec.id
        # Picking a model that cannot do the currently selected language means
        # the user chose the model on purpose; move the language to match
        # rather than transcribing Russian into an "English" setting.
        if not spec.supports(self.cfg.language):
            self.cfg.language = spec.fixed_language or "auto"
            self._sync_language_widgets()
        self.cfg.save()
        self.dictation.transcriber = Transcriber(self.cfg)
        self._refresh_chips()
        self._lang_note.configure(text=self._model_hint(spec))
        # Start fetching it now, while the user is still looking at Settings.
        # Otherwise the first dictation after a switch pays the whole download
        # — minutes, with the app apparently frozen mid-sentence.
        self._start_model_load()

    def _sync_language_widgets(self) -> None:
        """Push cfg.language back into the picker and the quick-switch button
        after something other than the picker changed it."""
        label = next((l[0] for l in LANGS if l[1] == self.cfg.language), None)
        if label is not None and getattr(self, "_lang_option_var", None) is not None:
            self._lang_option_var.set(label)
        if getattr(self, "lang_btn", None) is not None:
            self.lang_btn.configure(text=self._lang_abbr(self.cfg.language))

    def _set_lang(self, label: str) -> None:
        self.cfg.language = next(l[1] for l in LANGS if l[0] == label)
        self.cfg.save()
        self.lang_btn.configure(text=self._lang_abbr(self.cfg.language))

    def _set_threads(self, v: float) -> None:
        self.cfg.threads = int(round(v))
        self.cfg.save()
        self.thr_lbl.configure(text=i18n.t("rec.threads_label", n=self.cfg.threads))

    def _set_refine(self, v: int) -> None:
        self.cfg.refine_enabled = bool(v)
        self.cfg.save()
        self._build_chips()

    # ------------------------------------------------------- model load + progress

    def _alive(self, widget) -> bool:
        """Settings widgets die with their window; the pump outlives it."""
        try:
            return widget is not None and bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _model_status_text(self, text: str) -> None:
        if self._alive(getattr(self, "model_status", None)):
            self.model_status.configure(text=text)

    def _show_model_bar(self, fraction: float, done_mb: float, total_mb: float) -> None:
        text = i18n.t("rec.downloading", done=int(done_mb), total=int(total_mb),
                      percent=int(fraction * 100))
        bar = getattr(self, "model_bar", None)
        if self._alive(bar):
            if not bar.winfo_ismapped():
                bar.pack(fill="x", padx=14, pady=(4, 2))
            bar.set(fraction)
            self._model_status_text(text)
        try:
            self.sub_lbl.configure(text=text)
        except tk.TclError:
            pass

    def _hide_model_bar(self) -> None:
        bar = getattr(self, "model_bar", None)
        if self._alive(bar) and bar.winfo_ismapped():
            bar.pack_forget()

    def _start_model_load(self) -> None:
        """Fetch and initialise the model in the background, with progress.

        Called from the Settings button, at startup, and — the point of it —
        the moment the user picks a different model, so the download happens
        while they are still in Settings rather than in the middle of their
        next dictation.
        """
        if self.dictation.transcriber.is_loaded:
            self._model_status_text(i18n.t("common.model_loaded"))
            return
        self._model_status_text(i18n.t("common.loading_model"))

        def work() -> None:
            try:
                self.dictation.transcriber.load()
                msg = i18n.t("common.model_loaded")
            except Exception as exc:  # noqa: BLE001
                log.exception("model load failed")
                msg = i18n.t("common.error_with", error=exc)

            def done() -> None:
                self._hide_model_bar()
                self._model_status_text(msg)

            try:
                self.root.after(0, done)
            except RuntimeError:
                pass

        threading.Thread(target=work, daemon=True).start()
        self._pump_model_progress()

    def _pump_model_progress(self) -> None:
        """Redraw the download bar until the model is in memory."""
        if self._closing or self._model_pump_running:
            return
        self._model_pump_running = True
        self._tick_model_progress()

    def _tick_model_progress(self) -> None:
        if self._closing:
            self._model_pump_running = False
            return
        transcriber = self.dictation.transcriber
        progress = transcriber.progress
        if progress is not None:
            done_mb, total_mb = progress
            self._show_model_bar(done_mb / total_mb if total_mb else 0.0, done_mb, total_mb)
        if transcriber.is_loaded:
            self._model_pump_running = False
            self._hide_model_bar()
            return
        try:
            self.root.after(300, self._tick_model_progress)
        except RuntimeError:
            self._model_pump_running = False

    # ----------------------------------------------------------- hotkey capture

    def _capture_hotkey(self) -> None:
        self.hk_btn.configure(text=i18n.t("common.press_keys"))
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

    def _open_eventkauf(self) -> None:
        import webbrowser

        webbrowser.open("https://eventkauf.com")

    def _copy_pull_cmd(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append("ollama pull qwen2.5:3b")
        self.root.update_idletasks()
        self._pull_btn.configure(text=i18n.t("ref.copied_pull"))
        self.root.after(2500, lambda: self._pull_btn.configure(
            text=i18n.t("ref.btn_copy_pull")))

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
                    self.root.after(0, lambda: self._set_update_status(i18n.t("priv.no_updates")))
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
        self._set_update_status(i18n.t("upd.available_short", version=info.version))
        if self._update_banner is not None:
            return
        banner = ctk.CTkButton(
            self.root, text=i18n.t("upd.banner", version=info.version),
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
        win.title(i18n.t("upd.dialog_title"))
        win.geometry("480x420")
        win.configure(fg_color=theme.BG)
        win.transient(self.root)

        ctk.CTkLabel(win, text=f"WinDictoo {info.version}", font=_font(18, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(win, text=i18n.t("upd.whats_new"), font=_font(12, "bold"),
                     text_color=theme.MUTED).pack(anchor="w", padx=20)
        box = ctk.CTkTextbox(win, font=_font(12), fg_color=theme.CARD,
                             text_color=theme.TEXT, corner_radius=12, wrap="word")
        box.pack(fill="both", expand=True, padx=20, pady=8)
        box.insert("1.0", info.notes or i18n.t("upd.no_notes"))
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

        install_btn = ctk.CTkButton(btns, text=i18n.t("upd.btn_install"), fg_color=theme.ACCENT,
                                    hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                    font=_font(13, "bold"))
        install_btn.pack(side="right")
        ctk.CTkButton(btns, text=i18n.t("upd.btn_release_page"), fg_color=theme.CARD, hover_color=theme.CARD_HI,
                      text_color=theme.TEXT, command=open_page).pack(side="right", padx=8)
        ctk.CTkButton(btns, text=i18n.t("common.later"), fg_color="transparent", hover_color=theme.CARD,
                      text_color=theme.MUTED, command=later).pack(side="left")

        def do_install() -> None:
            install_btn.configure(state="disabled", text=i18n.t("upd.downloading"))
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
                        install_btn.configure(state="normal", text=i18n.t("upd.btn_install"))
                        status.configure(text=i18n.t("upd.failed", error=exc), text_color=theme.DANGER)

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

    # ----------------------------------------------------------- old installs

    def check_old_installs_async(self) -> None:
        """Renaming across VoxWin -> WnDic -> WinDictoo deliberately gave
        each name its own Inno Setup AppId, so a machine upgraded across
        renames (rather than freshly installed) ends up with leftover
        Start Menu entries and installed copies nobody asked for."""

        def work() -> None:
            found = oldversions.find_old_installs()
            if not found:
                return
            try:
                self.root.after(0, lambda: self._show_oldversions_banner(found))
            except RuntimeError:
                pass  # window already gone

        threading.Thread(target=work, daemon=True).start()

    def _show_oldversions_banner(self, found: list[tuple[str, str, str]] | None = None) -> None:
        if found is not None:
            self._oldversions_found = found
        if not self._oldversions_found or self._oldversions_banner is not None:
            return
        names = ", ".join(name for name, _, _ in self._oldversions_found)
        banner = ctk.CTkButton(
            self.root, text=i18n.t("old.banner", names=names),
            fg_color=theme.ACCENT_DIM, hover_color=theme.ACCENT_DIM, text_color=theme.TEXT,
            font=_font(12, "bold"), height=34, corner_radius=10,
            command=self._open_oldversions_dialog,
        )
        banner.pack(fill="x", padx=20, pady=(0, 6), before=self.hero_frame)
        self._oldversions_banner = banner

    def _hide_oldversions_banner(self) -> None:
        self._oldversions_found = []
        if self._oldversions_banner is not None:
            try:
                self._oldversions_banner.destroy()
            except tk.TclError:
                pass
            self._oldversions_banner = None

    def _open_oldversions_dialog(self) -> None:
        if not self._oldversions_found:
            return
        win = ctk.CTkToplevel(self.root)
        win.title(i18n.t("old.dialog_title"))
        win.geometry("440x320")
        win.configure(fg_color=theme.BG)
        win.transient(self.root)

        ctk.CTkLabel(win, text=i18n.t("old.found_title"), font=_font(16, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            win, text=i18n.t("old.explain"),
            font=_font(12), text_color=theme.MUTED, wraplength=400, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        rows = ctk.CTkFrame(win, fg_color=theme.CARD, corner_radius=theme.RADIUS_CARD,
                            border_width=1, border_color=theme.STROKE)
        rows.pack(fill="x", padx=20)
        for name, version, _ in self._oldversions_found:
            ctk.CTkLabel(rows, text=f"{name}  v{version}", font=_font(13),
                         text_color=theme.TEXT).pack(anchor="w", padx=14, pady=6)

        status = ctk.CTkLabel(win, text="", font=_font(11), text_color=theme.MUTED,
                              wraplength=400, justify="left")
        status.pack(anchor="w", padx=20, pady=(10, 0))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=20, side="bottom")

        def later() -> None:
            self._hide_oldversions_banner()
            try:
                win.destroy()
            except tk.TclError:
                pass

        def do_remove() -> None:
            remove_btn.configure(state="disabled", text=i18n.t("old.removing"))
            ok = all(oldversions.uninstall(cmd) for _, _, cmd in self._oldversions_found)
            oldversions.purge_stale_autostart_entries()
            status.configure(
                text=i18n.t("old.done_ok") if ok else i18n.t("old.done_partial"),
                text_color=theme.SUCCESS if ok else theme.WARN,
            )
            self._hide_oldversions_banner()
            win.after(2500, lambda: win.destroy() if win.winfo_exists() else None)

        remove_btn = ctk.CTkButton(btns, text=i18n.t("old.btn_remove"), fg_color=theme.ACCENT,
                                   hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                   font=_font(13, "bold"), command=do_remove)
        remove_btn.pack(side="right")
        ctk.CTkButton(btns, text=i18n.t("common.later"), fg_color="transparent", hover_color=theme.CARD,
                      text_color=theme.MUTED, command=later).pack(side="left")

    # ---------------------------------------------------------------- helpers

    def preload_model_async(self) -> None:
        """Load the recognition model in the background right after startup so
        the first dictation doesn't stall; the hero card shows what's
        happening. Also opens the microphone if the user asked for it to stay
        open, so the very first phrase gets the same instant start as the
        ones after it."""
        self.dictation.warm_up()
        if self.dictation.transcriber.is_loaded:
            return
        self.sub_lbl.configure(text=i18n.t("preload.loading"))
        # Draws the download bar on the hero card while the thread below runs.
        self._pump_model_progress()

        def work() -> None:
            try:
                self.dictation.transcriber.load()
                msg = i18n.t("common.model_loaded")
            except Exception as exc:  # noqa: BLE001
                log.exception("model preload failed")
                msg = i18n.t("preload.failed", error=exc)

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
        # Before tearing down the window: the capture stream can outlive a
        # dictation now, and a process that exits still holding it leaves the
        # Windows microphone-in-use indicator lit.
        try:
            self.dictation.shutdown()
        except Exception:  # noqa: BLE001
            log.exception("could not release the microphone on exit")
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self._on_quit()

    def run(self) -> None:
        self.root.mainloop()
