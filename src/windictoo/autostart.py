"""Launch-at-login via the HKCU Run registry key (no admin rights needed)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "WinDictoo"


def _launch_command() -> str:
    """The command that starts WinDictoo windowed (no console)."""
    # A frozen PyInstaller build is itself the launchable exe.
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray-only'
    # Otherwise prefer pythonw.exe so no console window appears.
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'"{exe}" -m windictoo --tray-only'


def is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except OSError:
        return False


def remove_legacy_startup_shortcut() -> None:
    """Older installers (pre-1.7.2) offered a separate "launch at startup"
    checkbox that dropped a Startup-folder shortcut independently of the
    Run-key toggle above — anyone who'd ticked both ended up with two
    WinDictoo entries in Task Manager's Startup tab. That installer task is
    gone; this deletes any shortcut it already left behind, so the Run key
    is the only autostart mechanism going forward. Safe to call every
    launch — a no-op once the shortcut is gone."""
    import os

    appdata = os.environ.get("APPDATA")
    if not appdata:
        # An empty/missing APPDATA must not fall back to a cwd-relative
        # path — that could point anywhere depending on where the process
        # happened to be launched from.
        return
    startup_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut = startup_dir / "WinDictoo.lnk"
    try:
        shortcut.unlink(missing_ok=True)
    except OSError:
        pass


def set_enabled(enabled: bool) -> str | None:
    """Returns None on success or an error message."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, _VALUE_NAME, 0, winreg.REG_SZ, _launch_command()
                )
                log.info("autostart enabled")
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                    log.info("autostart disabled")
                except FileNotFoundError:
                    pass
        return None
    except OSError as exc:
        log.warning("autostart change failed: %s", exc)
        return str(exc)
