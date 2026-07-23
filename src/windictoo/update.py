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

        asset = next(
            (a for a in data.get("assets", []) if a.get("name", "").endswith(".exe")),
            None,
        )
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
