"""GitHub release update check and self-update for the packaged GUI.

Uses only the standard library so it works inside the PyQt-only frozen GUI
(no extra runtime dependencies, no PyQt6.QtNetwork).
"""

from __future__ import annotations

import json
import ssl
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pygiffer.version import __version__, is_newer

GITHUB_REPO = "rcy17/pygiffer"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_USER_AGENT = f"PyGiffer/{__version__}"
_TIMEOUT = 10


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    asset_url: str
    asset_name: str

    @property
    def is_update(self) -> bool:
        return is_newer(self.version, __version__)


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    return ctx


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"})


def fetch_latest_release() -> ReleaseInfo:
    """Query the latest GitHub release. Raises on network/parse failure."""
    with urllib.request.urlopen(_request(_LATEST_RELEASE_API), timeout=_TIMEOUT, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        raise ValueError("release has no tag_name")

    assets = data.get("assets") or []
    asset_url = ""
    asset_name = ""
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.lower().endswith(".zip"):
            asset_url = str(asset.get("browser_download_url", ""))
            asset_name = name
            break

    return ReleaseInfo(
        tag=tag,
        version=tag.lstrip("vV"),
        asset_url=asset_url,
        asset_name=asset_name or "pygiffer-windows.zip",
    )


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    """Directory that contains pygiffer.exe (the release root)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def download_release(info: ReleaseInfo, progress=None) -> Path:
    """Download the release zip to a temp file. Returns the local path.

    ``progress`` is an optional callable(downloaded_bytes, total_bytes).
    """
    if not info.asset_url:
        raise ValueError("release has no downloadable .zip asset")

    tmp_dir = Path(tempfile.mkdtemp(prefix="pygiffer-update-"))
    target = tmp_dir / info.asset_name

    with urllib.request.urlopen(_request(info.asset_url), timeout=_TIMEOUT, context=_ssl_context()) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        chunk = 1024 * 64
        with open(target, "wb") as fh:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                if progress is not None:
                    progress(done, total)
    return target


def extract_release(zip_path: Path) -> Path:
    """Extract the release zip and return the folder holding pygiffer.exe."""
    out_dir = zip_path.parent / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)

    # The zip may contain a top-level "pygiffer" folder or the files directly.
    for candidate in [out_dir, *sorted(p for p in out_dir.rglob("pygiffer.exe"))]:
        if candidate.is_file() and candidate.name == "pygiffer.exe":
            return candidate.parent
    if (out_dir / "pygiffer.exe").exists():
        return out_dir
    raise FileNotFoundError("pygiffer.exe not found in release archive")


def _build_updater_bat(new_dir: Path, install_dir: Path) -> Path:
    """Write a batch script that swaps files and re-runs install_registry."""
    bat = new_dir.parent / "pygiffer-apply-update.bat"
    # robocopy exit codes 0-7 are success; treat >=8 as failure.
    content = f"""@echo off
setlocal EnableExtensions
title PyGiffer Updater
echo Waiting for PyGiffer to close...
:waitloop
tasklist /FI "IMAGENAME eq pygiffer.exe" 2>nul | find /I "pygiffer.exe" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)

echo Updating files...
robocopy "{new_dir}" "{install_dir}" /E /IS /IT /R:3 /W:1 /NFL /NDL /NJH /NJS >nul
if %ERRORLEVEL% GEQ 8 (
    echo Update failed while copying files.
    pause
    exit /b 1
)

echo Registering context menu...
call "{install_dir}\\install_registry.bat"

echo Restarting PyGiffer...
start "" "{install_dir}\\pygiffer.exe"
exit /b 0
"""
    bat.write_text(content, encoding="utf-8")
    return bat


def launch_update(new_dir: Path, install_dir: Path) -> None:
    """Launch the detached updater and let the caller exit to release locks."""
    bat = _build_updater_bat(new_dir, install_dir)
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP so it outlives this process.
    flags = 0x00000008 | 0x00000200
    import subprocess

    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=flags,
        close_fds=True,
        cwd=str(new_dir.parent),
    )
