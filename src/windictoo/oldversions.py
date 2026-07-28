"""Detect leftover installs from earlier names of this project.

WinDictoo went through two renames (VoxWin -> WnDic -> WinDictoo), and each
used a fresh Inno Setup AppId on purpose so the previous name's uninstaller
kept working independently — but nothing ever prompted the user to actually
run it. A machine that was upgraded across renames (rather than a clean
install) ends up with two or three separate Start Menu entries and installed
copies that nobody asked for.
"""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)

# (display name, Inno Setup AppId) for every name this project has shipped
# under before "WinDictoo". Never add the current name here.
_OLD_APPIDS = [
    ("VoxWin", "{D18B4F56-3DDE-4A7C-9D90-B05C1ABC56DD}"),
    ("WnDic", "{96621E0E-70BA-4E02-8995-92101C7E48D5}"),
]


def find_old_installs() -> list[tuple[str, str, str]]:
    """Return [(display_name, version, uninstall_command), ...] for each old
    name still present in Add/Remove Programs. Never raises."""
    import winreg

    found = []
    for name, appid in _OLD_APPIDS:
        key_path = (
            rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{appid}_is1"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                uninstall_cmd = winreg.QueryValueEx(key, "UninstallString")[0]
                found.append((name, version, uninstall_cmd))
        except OSError:
            continue
    return found


def uninstall(uninstall_cmd: str) -> bool:
    """Run a previous version's own uninstaller silently. Returns True if the
    process launched (not whether it succeeded — Inno's uninstaller doesn't
    report that synchronously without a wait, and callers don't need to
    block the UI on it)."""
    try:
        exe, *rest = _split_uninstall_command(uninstall_cmd)
        subprocess.Popen(  # noqa: S603
            [exe, *rest, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
        )
        return True
    except Exception:  # noqa: BLE001
        log.exception("could not launch uninstaller: %s", uninstall_cmd)
        return False


def _split_uninstall_command(cmd: str) -> list[str]:
    """UninstallString is typically '"C:\\...\\unins000.exe"' — a quoted
    path with no extra arguments in Inno Setup's default output."""
    cmd = cmd.strip()
    if cmd.startswith('"'):
        end = cmd.find('"', 1)
        if end != -1:
            return [cmd[1:end], *cmd[end + 1:].split()]
    return cmd.split()
