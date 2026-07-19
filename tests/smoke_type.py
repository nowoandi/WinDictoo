"""Live proof that dictated text lands in a focused field (SendInput typing).

Creates a real window with an Entry, gives it focus, types via the same
insert.type_unicode() the app uses, and reads the field back. This needs an
interactive desktop with foreground focus, so it is a standalone smoke script
(not a pytest test, which runs without reliable window focus).
Run: uv run python tests/smoke_type.py
"""

from __future__ import annotations

import time
import tkinter as tk

from windictoo import insert

PHRASE = "Привет мир 42 — Grüße"


def main() -> int:
    root = tk.Tk()
    root.title("WinDictoo type test")
    root.geometry("360x100+240+240")
    entry = tk.Entry(root, width=48)
    entry.pack(padx=12, pady=24)
    root.deiconify()
    root.attributes("-topmost", True)

    got = ""
    # Routing injected keys to our window needs it to be the OS foreground
    # window, which an automated desktop grants only intermittently. Retry a
    # few times; on a real interactive desktop the first attempt succeeds.
    for attempt in range(5):
        entry.delete(0, "end")
        root.lift()
        root.focus_force()
        entry.focus_force()
        for _ in range(25):
            root.update()
            time.sleep(0.02)
        insert.type_unicode(PHRASE)
        for _ in range(60):
            root.update()
            time.sleep(0.02)
        got = entry.get()
        print(f"[i] attempt {attempt + 1}: field={got!r}")
        if PHRASE in got:
            break

    root.destroy()
    passed = PHRASE in got
    print("[OK] text landed in the focused field" if passed else "[FAIL] no foreground focus in this session")
    print("=== TYPE SMOKE PASSED ===" if passed else "=== TYPE SMOKE INCONCLUSIVE (no interactive foreground) ===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
