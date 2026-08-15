"""Check github.com/nowoandi/WinDictoo releases for a newer version.

Network-only, best-effort: any failure (offline, rate limit, no assets)
returns None rather than raising — an update check must never break startup
or dictation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

REPO = "nowoandi/WinDictoo"
_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_TIMEOUT = 6.0


@dataclass
class UpdateInfo:
    version: str  # e.g. "1.4.0" (no leading "v")
    notes: str  # release body (markdown), as written on GitHub
    download_url: str  # direct link to the .exe installer asset
    release_url: str  # human-facing release page, as a fallback


def _parse_version(tag: str) -> tuple[int, ...] | None:
    raw = tag.strip().lstrip("vV")
    try:
        return tuple(int(p) for p in raw.split("."))
    except ValueError:
        return None


def is_newer(remote: str, current: str) -> bool:
    r, c = _parse_version(remote), _parse_version(current)
    if r is None or c is None:
        return False
    return r > c


def _pick_asset(assets: list[dict]) -> dict | None:
    """Choose the download asset: the installer if present, else any exe.

    Builds up to 1.7.3 had no such preference — they took the first .exe the
    API returned. GitHub returns assets sorted by name, compared without
    regard to case, so "WinDictoo-1.7.4-portable.exe" came before
    "WinDictoo-Setup-1.7.4.exe" (a digit sorts ahead of any letter). Those
    builds therefore downloaded the portable copy, saved it as
    "…-Setup-….exe" and ran it: it installed nothing, so the same update was
    offered again at every start, forever, and the fix could never arrive
    through the mechanism that was broken.

    The rescue is in the *name*: installer assets are published as
    "WinDictoo-<version>-Install-Setup.exe", which sorts ahead of "portable"
    either way, so even an unpatched 1.7.3 now picks up a real installer.
    Keep that naming (see packaging/WinDictoo-Setup.iss). This function is
    the belt to that pair of braces, and accepts either wording.
    """
    exes = [a for a in assets if a.get("name", "").lower().endswith(".exe")]
    installers = [
        a for a in exes
        if "setup" in a.get("name", "").lower() or "install" in a.get("name", "").lower()
    ]
    return installers[0] if installers else (exes[0] if exes else None)


def check_for_update(current_version: str) -> UpdateInfo | None:
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(_API_URL, headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            data = resp.json()

        tag = data.get("tag_name", "")
        version = tag.lstrip("vV")
        if not is_newer(version, current_version):
            return None

        asset = _pick_asset(data.get("assets", []))
        if asset is None:
            return None

        return UpdateInfo(
            version=version,
            notes=data.get("body", "").strip(),
            download_url=asset["browser_download_url"],
            release_url=data.get("html_url", f"https://github.com/{REPO}/releases"),
        )
    except Exception as exc:  # noqa: BLE001 - never let an update check crash the app
        log.info("update check failed (offline or rate-limited): %s", exc)
        return None


def download_installer(url: str, dest_path: str, timeout: float = 120.0) -> None:
    """Stream the installer .exe to `dest_path`. Raises on any failure."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1 << 16):
                    f.write(chunk)
