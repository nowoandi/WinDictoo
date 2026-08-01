"""First-run wizard (CustomTkinter): welcome → mic → model → hotkey → test → done."""

from __future__ import annotations

import threading

import customtkinter as ctk

from . import i18n, theme
from .app import Dictation, State
from .audio import Recorder, input_devices
from .config import Config
from .hotkey import describe
from .widgets import Equalizer

STEPS = ["welcome", "microphone", "model", "hotkey", "test", "done"]


def _models() -> list[tuple[str, str]]:
    return [
        (i18n.t("ob.model_tiny"), "tiny"),
        (i18n.t("ob.model_base"), "base"),
        (i18n.t("ob.model_small"), "small"),
        (i18n.t("ob.model_medium"), "medium"),
    ]


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


class Onboarding:
    def __init__(self, parent, cfg: Config, dictation: Dictation, apply_hotkey, on_finish,
                 stop_hotkey=None) -> None:
        self.cfg = cfg
        self.dictation = dictation
        self.apply_hotkey = apply_hotkey
        self.stop_hotkey = stop_hotkey
        self.on_finish = on_finish
        self.i = 0
        self._probe: Recorder | None = None
        # Pending after()-callback of the dictation-test watcher, so leaving
        # the step can cancel it (otherwise it fires on destroyed widgets).
        self._watch_id: str | None = None

        self.win = ctk.CTkToplevel(parent)
        self.win.title(i18n.t("ob.window_title"))
        self.win.geometry("580x520")
        self.win.configure(fg_color=theme.BG)
        self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._skip_all)

        # progress dots
        self.dots = ctk.CTkFrame(self.win, fg_color="transparent")
        self.dots.pack(fill="x", padx=28, pady=(18, 0))
        self._dot_lbls = []
        for _ in STEPS:
            d = ctk.CTkLabel(self.dots, text="●", font=_font(14), text_color=theme.STROKE)
            d.pack(side="left", padx=3)
            self._dot_lbls.append(d)

        self.card = ctk.CTkFrame(self.win, fg_color=theme.CARD,
                                 corner_radius=theme.RADIUS_CONTAINER,
                                 border_width=1, border_color=theme.STROKE)
        self.card.pack(fill="both", expand=True, padx=24, pady=16)

        nav = ctk.CTkFrame(self.win, fg_color="transparent")
        nav.pack(fill="x", padx=24, pady=(0, 18))
        self.back_btn = ctk.CTkButton(nav, text=i18n.t("ob.btn_back"), width=90, fg_color=theme.CARD,
                                       hover_color=theme.CARD_HI, text_color=theme.TEXT,
                                       corner_radius=theme.RADIUS_BUTTON, border_width=1,
                                       border_color=theme.STROKE, command=self._back)
        self.back_btn.pack(side="left")
        ctk.CTkButton(nav, text=i18n.t("ob.btn_skip"), width=110, fg_color="transparent",
                      hover_color=theme.CARD, text_color=theme.MUTED,
                      corner_radius=theme.RADIUS_BUTTON, command=self._skip_all).pack(side="left", padx=8)
        self.next_btn = ctk.CTkButton(nav, text=i18n.t("ob.btn_next"), width=150, fg_color=theme.ACCENT,
                                       hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                       font=_font(14, "bold"),
                                       corner_radius=theme.RADIUS_BUTTON, command=self._next)
        self.next_btn.pack(side="right")

        self._render()

    # navigation -----------------------------------------------------------

    def _next(self) -> None:
        if STEPS[self.i] == "done":
            self._finish()
            return
        self.i = min(self.i + 1, len(STEPS) - 1)
        self._render()

    def _back(self) -> None:
        self._stop_probe()
        self.i = max(self.i - 1, 0)
        self._render()

    def _skip_all(self) -> None:
        self._finish()

    def _finish(self) -> None:
        self._stop_probe()
        self._stop_test()
        self.cfg.onboarding_done = True
        self.cfg.save()
        try:
            self.win.destroy()
        except Exception:  # noqa: BLE001
            pass
        self.on_finish()

    def _clear(self) -> None:
        for w in self.card.winfo_children():
            w.destroy()

    def _title(self, icon: str, text: str) -> None:
        row = ctk.CTkFrame(self.card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(24, 10))
        ctk.CTkLabel(row, text=icon, font=_font(30)).pack(side="left")
        ctk.CTkLabel(row, text=text, font=_font(20, "bold"), text_color=theme.TEXT).pack(side="left", padx=12)

    def _text(self, s: str) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(self.card, text=s, font=_font(13), text_color=theme.MUTED,
                           justify="left", wraplength=480)
        lbl.pack(anchor="w", padx=28, pady=2)
        return lbl

    def _render(self) -> None:
        # Leaving a step must stop anything it started: the mic probe and a
        # still-running dictation test both keep going otherwise.
        self._stop_probe()
        self._stop_test()
        self._clear()
        for j, d in enumerate(self._dot_lbls):
            d.configure(text_color=theme.ACCENT if j == self.i else theme.STROKE)
        self.back_btn.configure(state="normal" if self.i > 0 else "disabled")
        self.next_btn.configure(text=i18n.t("ob.btn_start_using") if STEPS[self.i] == "done" else i18n.t("ob.btn_next"))
        getattr(self, f"_step_{STEPS[self.i]}")()

    # steps ----------------------------------------------------------------

    def _step_welcome(self) -> None:
        self._title("👋", i18n.t("ob.welcome_title"))
        self._text(i18n.t("ob.welcome_text"))
        # "Hello" in every interface language the app ships with — says
        # "this speaks your language" at a glance, which three lines of
        # feature bullets did not.
        ctk.CTkLabel(self.card, text="  ·  ".join(i18n.GREETINGS),
                     font=_font(14, "bold"), text_color=theme.ACCENT,
                     wraplength=490, justify="center").pack(padx=28, pady=(18, 6))

    def _step_microphone(self) -> None:
        self._title("🎙", i18n.t("ob.mic_title"))
        devices = input_devices()
        self._text(i18n.t("ob.mic_found", n=len(devices)) if devices else i18n.t("ob.mic_none"))
        self._eq = Equalizer(self.card, width=400, height=54, bg=theme.CARD)
        self._eq.pack(pady=10)
        self._mic_btn = ctk.CTkButton(self.card, text=i18n.t("ob.mic_btn_test"), fg_color=theme.ACCENT,
                                      hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                      corner_radius=theme.RADIUS_BUTTON,
                                      command=self._toggle_probe)
        self._mic_btn.pack(pady=4)
        self._text(i18n.t("ob.mic_hint"))

    def _step_model(self) -> None:
        self._title("◈", i18n.t("ob.model_title"))
        self._text(i18n.t("ob.model_text"))
        self._model_var = ctk.StringVar(value=self.cfg.model)
        for label, name in _models():
            ctk.CTkRadioButton(self.card, text=label, variable=self._model_var, value=name,
                               font=_font(13), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                               command=self._pick_model).pack(anchor="w", padx=32, pady=4)
        self._model_status = ctk.CTkLabel(self.card, text="", font=_font(12), text_color=theme.SUCCESS)
        self._model_status.pack(anchor="w", padx=32, pady=6)
        ctk.CTkButton(self.card, text=i18n.t("ob.btn_load_now"), fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                      corner_radius=theme.RADIUS_BUTTON,
                      command=self._download_model).pack(anchor="w", padx=32)

    def _step_hotkey(self) -> None:
        self._title("⌨", i18n.t("ob.hotkey_title"))
        self._text(i18n.t("ob.hotkey_text", hotkey=describe(self.cfg.hotkey)))
        self._hk_btn = ctk.CTkButton(self.card, text=describe(self.cfg.hotkey), fg_color=theme.ACCENT,
                                     hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                     width=200,
                                     corner_radius=theme.RADIUS_BUTTON, command=self._capture_hotkey)
        self._hk_btn.pack(padx=32, pady=12)
        self._hk_err = ctk.CTkLabel(self.card, text="", font=_font(11), text_color=theme.DANGER)
        self._hk_err.pack(anchor="w", padx=32)
        self._text(i18n.t("ob.hotkey_hint"))

    def _step_test(self) -> None:
        self._title("🎤", i18n.t("ob.test_title"))
        self._text(i18n.t("ob.test_text"))
        self._test_btn = ctk.CTkButton(self.card, text=i18n.t("ob.test_btn_start"), fg_color=theme.ACCENT,
                                       hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                       corner_radius=theme.RADIUS_BUTTON,
                                       command=self._toggle_test)
        self._test_btn.pack(padx=32, pady=8)
        self._test_state = ctk.CTkLabel(self.card, text="", font=_font(12), text_color=theme.MUTED)
        self._test_state.pack(anchor="w", padx=32)
        self._test_box = ctk.CTkTextbox(self.card, font=_font(13), fg_color=theme.CARD_HI,
                                        text_color=theme.TEXT, corner_radius=theme.RADIUS_WIDGET,
                                        border_width=1, border_color=theme.STROKE,
                                        height=90, wrap="word")
        self._test_box.pack(fill="x", padx=28, pady=8)

    def _step_done(self) -> None:
        self._title("✓", i18n.t("ob.done_title"))
        self._text(i18n.t("ob.done_text", hotkey=describe(self.cfg.hotkey)))

    # actions --------------------------------------------------------------

    def _toggle_probe(self) -> None:
        if self._probe is not None:
            self._stop_probe()
            self._mic_btn.configure(text=i18n.t("ob.mic_btn_test"))
            return
        self._probe = Recorder()
        try:
            self._probe.start()
        except Exception as exc:  # noqa: BLE001
            self._mic_btn.configure(text=i18n.t("common.error_with", error=exc))
            self._probe = None
            return
        self._mic_btn.configure(text=i18n.t("ob.mic_btn_stop"))
        self._eq.set_active(True)
        self._pump_probe()

    def _pump_probe(self) -> None:
        if self._probe is not None and self._probe.is_recording:
            self._eq.set_level(self._probe.level)
            self.win.after(50, self._pump_probe)

    def _stop_probe(self) -> None:
        if self._probe is not None:
            self._probe.cancel()
            self._probe = None

    def _stop_test(self) -> None:
        """Cancel the dictation test and its UI watcher (step change/close)."""
        if self._watch_id is not None:
            try:
                self.win.after_cancel(self._watch_id)
            except Exception:  # noqa: BLE001
                pass
            self._watch_id = None
        if self.dictation.sink is not None:
            self.dictation.sink = None
            if self.dictation.state is State.RECORDING:
                self.dictation.cancel()

    def _pick_model(self) -> None:
        self.cfg.model = self._model_var.get()
        self.cfg.save()
        from .transcribe import Transcriber

        self.dictation.transcriber = Transcriber(self.cfg)

    def _download_model(self) -> None:
        self._pick_model()
        self._model_status.configure(text=i18n.t("common.loading_model"), text_color=theme.MUTED)

        def work() -> None:
            try:
                self.dictation.transcriber.load()
                self.win.after(0, lambda: self._model_status.configure(
                    text=i18n.t("common.model_loaded"), text_color=theme.SUCCESS))
            except Exception as exc:  # noqa: BLE001
                self.win.after(0, lambda: self._model_status.configure(
                    text=i18n.t("common.error_with", error=exc), text_color=theme.DANGER))

        threading.Thread(target=work, daemon=True).start()

    def _capture_hotkey(self) -> None:
        self._hk_btn.configure(text=i18n.t("common.press_keys"))
        mods: list[str] = []
        from .gui import _MOD_KEYSYMS, WinDictooGUI

        if self.stop_hotkey is not None:
            self.stop_hotkey()

        def finish(spec: list[str] | None) -> None:
            self.win.unbind("<KeyPress>", bid)
            if spec is None:
                self.apply_hotkey(self.cfg.hotkey)
                self._hk_btn.configure(text=describe(self.cfg.hotkey))
                return
            err = self.apply_hotkey(spec)
            if err:
                self.apply_hotkey(self.cfg.hotkey)
                self._hk_err.configure(text=err)
                self._hk_btn.configure(text=describe(self.cfg.hotkey))
            else:
                self.cfg.hotkey = spec
                self.cfg.save()
                self._hk_btn.configure(text=describe(spec))

        def on_press(event) -> str:
            ks = event.keysym
            if ks in _MOD_KEYSYMS:
                if _MOD_KEYSYMS[ks] not in mods:
                    mods.append(_MOD_KEYSYMS[ks])
                return "break"
            if ks == "Escape":
                finish(None)
                return "break"
            main = WinDictooGUI._keysym_to_token(ks)
            if main is None:
                return "break"
            finish(mods + [main])
            return "break"

        bid = self.win.bind("<KeyPress>", on_press)
        self.win.focus_force()

    def _toggle_test(self) -> None:
        if self.dictation.state is State.RECORDING:
            self.dictation.stop_and_process()
            return
        if self.dictation.state is not State.IDLE:
            return
        self._test_box.delete("1.0", "end")

        def sink(text: str) -> None:
            self.win.after(0, lambda: (self._test_box.delete("1.0", "end"),
                                       self._test_box.insert("1.0", text or i18n.t("main.result_empty"))))
            self.dictation.sink = None

        self.dictation.sink = sink
        self.dictation.start()
        self._test_btn.configure(text=i18n.t("ob.mic_btn_stop"))
        self._watch_test()

    def _watch_test(self) -> None:
        self._watch_id = None
        try:
            if not self._test_state.winfo_exists():
                return
            st = self.dictation.state
            self._test_state.configure(text={
                State.RECORDING: i18n.t("state.recording"),
                State.TRANSCRIBING: i18n.t("state.transcribing"),
            }.get(st, ""))
            if st in (State.IDLE, State.DONE, State.CANCELLED, State.ERROR):
                self._test_btn.configure(text=i18n.t("ob.test_btn_start"))
            else:
                self._watch_id = self.win.after(200, self._watch_test)
        except Exception:  # noqa: BLE001  (step left mid-poll — widgets gone)
            pass
