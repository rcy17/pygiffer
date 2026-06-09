"""GitHub release update check and self-update for the packaged GUI.

Uses only the standard library so it works inside the PyQt-only frozen GUI
(no extra runtime dependencies, no PyQt6.QtNetwork).

The release is published as a *layered* set of assets:

* ``manifest.json``        - describes the release (version, depskey, asset names)
* ``pygiffer-app-*.zip``   - the small, frequently-changing application files
* ``pygiffer-deps-*.zip``  - the large third-party libraries (cv2/PyQt6/numpy/...)

The deps zip is keyed by ``depskey`` (a hash of the locked dependency set). When
the locally installed depskey already matches the release, the heavy deps zip is
*not* downloaded again - only the small app zip is fetched.

Downloads are cached on disk and resumable (HTTP Range). The cache is cleared
only after the update is applied successfully.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from pygiffer.version import __version__, is_newer

GITHUB_REPO = "rcy17/pygiffer"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_USER_AGENT = f"PyGiffer/{__version__}"
_TIMEOUT = 30
_CHUNK = 1024 * 64

# Top-level entries inside _internal/ that hold the large third-party libraries.
# These rarely change between releases, so they ship in a separate "deps" zip.
DEPS_INTERNAL_DIRS = ["cv2", "PyQt6", "numpy", "numpy.libs", "PIL"]

DEPS_KEY_FILE = "deps.key"


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    assets: dict[str, str] = field(default_factory=dict)  # name -> download url

    @property
    def is_update(self) -> bool:
        return is_newer(self.version, __version__)

    def first_zip(self) -> tuple[str, str] | None:
        for name, url in self.assets.items():
            if name.lower().endswith(".zip"):
                return name, url
        return None


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _request(url: str, extra_headers: dict | None = None) -> urllib.request.Request:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"}
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, headers=headers)


def fetch_latest_release() -> ReleaseInfo:
    """Query the latest GitHub release. Raises on network/parse failure."""
    with urllib.request.urlopen(_request(_LATEST_RELEASE_API), timeout=_TIMEOUT, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        raise ValueError("release has no tag_name")

    assets: dict[str, str] = {}
    for asset in data.get("assets") or []:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name and url:
            assets[name] = url

    return ReleaseInfo(tag=tag, version=tag.lstrip("vV"), assets=assets)


def fetch_manifest(info: ReleaseInfo) -> dict | None:
    """Download and parse manifest.json from a release, or None if absent."""
    url = info.assets.get("manifest.json")
    if not url:
        return None
    with urllib.request.urlopen(_request(url), timeout=_TIMEOUT, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    """Directory that contains pygiffer.exe (the release root)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def update_cache_dir() -> Path:
    """Persistent cache for downloaded update assets (survives app restarts)."""
    base = Path.home() / ".pygiffer" / "update-cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def installed_depskey() -> str:
    """Read the depskey of the currently installed third-party libraries."""
    key_file = install_root() / DEPS_KEY_FILE
    try:
        return key_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _is_complete(path: Path, size: int, sha: str) -> bool:
    if not path.exists():
        return False
    if sha:
        return _sha256(path) == sha.lower()
    if size:
        return path.stat().st_size == size
    return True


def download_asset(url: str, dest: Path, size: int = 0, sha: str = "", progress=None) -> Path:
    """Download ``url`` to ``dest`` with resume support and integrity check.

    ``progress`` is an optional callable(downloaded_bytes, total_bytes).
    A cached, complete file is reused without re-downloading.
    """
    if not url:
        raise ValueError("missing asset download url")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if _is_complete(dest, size, sha):
        if progress is not None:
            n = dest.stat().st_size
            progress(n, n)
        return dest

    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if part.exists() else 0

    headers = {"Range": f"bytes={existing}-"} if existing else None
    with urllib.request.urlopen(_request(url, headers), timeout=_TIMEOUT, context=_ssl_context()) as resp:
        # 206 => server honoured our Range and we can append; otherwise restart.
        resume = existing > 0 and getattr(resp, "status", resp.getcode()) == 206
        mode = "ab" if resume else "wb"
        if not resume:
            existing = 0
        total = existing + int(resp.headers.get("Content-Length", 0) or 0)
        done = existing
        with open(part, mode) as fh:
            while True:
                block = resp.read(_CHUNK)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                if progress is not None:
                    progress(done, total)

    if sha and _sha256(part) != sha.lower():
        part.unlink(missing_ok=True)
        raise ValueError(f"checksum mismatch for {dest.name}")

    os.replace(part, dest)
    return dest


def _extract(zip_path: Path, dest_dir: Path) -> Path:
    """Extract ``zip_path`` into a freshly-cleaned ``dest_dir``."""
    if dest_dir.exists():
        import shutil

        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    return dest_dir


def _resolve_payload_root(extracted: Path) -> Path:
    """Return the folder whose contents should be copied over the install dir.

    Handles archives that wrap everything in a single top-level folder.
    """
    if (extracted / "pygiffer.exe").exists() or (extracted / "_internal").exists():
        return extracted
    entries = [p for p in extracted.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted


@dataclass
class UpdatePlan:
    app_dir: str
    deps_dir: str  # "" when deps are reused (not re-downloaded)
    depskey: str   # "" for legacy single-zip releases
    install_dir: str
    cache_dir: str


def prepare_update(info: ReleaseInfo, manifest: dict | None, progress=None) -> UpdatePlan:
    """Download the needed assets into the cache and extract them.

    Returns an :class:`UpdatePlan` describing what to copy on apply.
    """
    cache = update_cache_dir()
    install_dir = install_root()

    if not manifest:
        # Legacy single-zip release: download and extract everything.
        zip_info = info.first_zip()
        if not zip_info:
            raise ValueError("release has no downloadable .zip asset")
        name, url = zip_info
        zip_path = download_asset(url, cache / name, progress=progress)
        app_dir = _resolve_payload_root(_extract(zip_path, cache / "app"))
        return UpdatePlan(str(app_dir), "", "", str(install_dir), str(cache))

    depskey = str(manifest.get("depskey", ""))
    app = manifest.get("app") or {}
    deps = manifest.get("deps") or {}

    app_name = app.get("name", "")
    app_url = info.assets.get(app_name)
    if not app_url:
        raise ValueError(f"app asset '{app_name}' not found in release")

    need_deps = bool(deps) and depskey and installed_depskey() != depskey
    app_size = int(app.get("size", 0) or 0)
    deps_size = int(deps.get("size", 0) or 0) if need_deps else 0
    grand_total = app_size + deps_size
    base = {"offset": 0}

    def combined(file_done: int, _file_total: int) -> None:
        if progress is not None:
            progress(base["offset"] + file_done, grand_total or 0)

    app_zip = download_asset(app_url, cache / app_name, app_size, app.get("sha256", ""), combined)
    base["offset"] = app_size

    deps_dir = ""
    if need_deps:
        deps_name = deps.get("name", "")
        deps_url = info.assets.get(deps_name)
        if not deps_url:
            raise ValueError(f"deps asset '{deps_name}' not found in release")
        deps_zip = download_asset(deps_url, cache / deps_name, deps_size, deps.get("sha256", ""), combined)
        deps_dir = str(_extract(deps_zip, cache / "deps"))

    app_dir = str(_resolve_payload_root(_extract(app_zip, cache / "app")))
    return UpdatePlan(app_dir, deps_dir, depskey, str(install_dir), str(cache))


def _robocopy_line(src: str, dst: str) -> str:
    # robocopy exit codes 0-7 are success; >=8 is failure.
    return (
        f'robocopy "{src}" "{dst}" /E /IS /IT /R:2 /W:1 /NFL /NDL /NJH /NJS >nul\r\n'
        f"if %ERRORLEVEL% GEQ 8 goto fail\r\n"
    )


def build_apply_script(plan: UpdatePlan) -> Path:
    """Write the batch script that swaps files and relaunches the app.

    The script lives in %TEMP% (not the cache) so it can delete the cache at
    the end. It runs in its own console window so timeout/start/pause work.
    """
    install_dir = plan.install_dir
    parts = [
        "@echo off\r\n",
        "setlocal EnableExtensions\r\n",
        "title PyGiffer Updater\r\n",
        "echo Installing PyGiffer update, please wait...\r\n",
        "set /a tries=0\r\n",
        ":waitloop\r\n",
        'tasklist /FI "IMAGENAME eq pygiffer.exe" 2>nul | find /I "pygiffer.exe" >nul\r\n',
        "if errorlevel 1 goto docopy\r\n",
        "set /a tries+=1\r\n",
        "if %tries% GEQ 60 goto docopy\r\n",
        "ping -n 2 127.0.0.1 >nul\r\n",
        "goto waitloop\r\n",
        ":docopy\r\n",
        "echo Updating application files...\r\n",
        _robocopy_line(plan.app_dir, install_dir),
    ]
    if plan.deps_dir:
        parts.append("echo Updating library files...\r\n")
        parts.append(_robocopy_line(plan.deps_dir, install_dir))
    if plan.depskey:
        parts.append(f'> "{install_dir}\\{DEPS_KEY_FILE}" echo {plan.depskey}\r\n')
    parts += [
        "echo Registering context menu...\r\n",
        f'call "{install_dir}\\install_registry.bat" nopause\r\n',
        "echo Cleaning up...\r\n",
        f'rmdir /S /Q "{plan.cache_dir}" 2>nul\r\n',
        "echo Restarting PyGiffer...\r\n",
        f'start "" "{install_dir}\\pygiffer.exe"\r\n',
        "exit /b 0\r\n",
        ":fail\r\n",
        "echo.\r\n",
        "echo Update failed while copying files. Your installation is unchanged.\r\n",
        "echo The download cache is kept so the next attempt can resume.\r\n",
        "pause\r\n",
        "exit /b 1\r\n",
    ]

    fd, tmp = tempfile.mkstemp(prefix="pygiffer-apply-", suffix=".bat")
    os.close(fd)
    bat = Path(tmp)
    bat.write_text("".join(parts), encoding="utf-8")
    return bat


def launch_update(plan: UpdatePlan) -> None:
    """Launch the updater in a new console window and let the caller exit."""
    bat = build_apply_script(plan)
    # CREATE_NEW_CONSOLE so the script has a real console (timeout/start/pause
    # all work); CREATE_NEW_PROCESS_GROUP so it survives this process exiting.
    flags = 0x00000010 | 0x00000200
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=flags,
        close_fds=True,
        cwd=tempfile.gettempdir(),
    )
