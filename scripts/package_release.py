"""Package the PyInstaller onedir output into layered release assets.

Produces, next to ``dist/pygiffer``:

* ``pygiffer-app-<version>-windows.zip``   - small, changes every release
* ``pygiffer-deps-<depskey>-windows.zip``  - large 3rd-party libs (cv2/PyQt6/...)
* ``manifest.json``                        - describes the release

``depskey`` is a short hash of the locked dependency versions, so the deps zip
keeps the same identity across releases whenever the dependencies are unchanged.
The auto-updater uses this to skip re-downloading the heavy libraries.

Shared by both build_release.bat and the CI release workflow.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pygiffer.updater import DEPS_INTERNAL_DIRS  # noqa: E402
from pygiffer.version import __version__  # noqa: E402

DIST = ROOT / "dist" / "pygiffer"
OUT = ROOT / "dist"

# Packages whose versions define the deps layer identity.
_DEP_PACKAGES = ["PyQt6", "PyQt6-Qt6", "PyQt6-sip", "opencv-python-headless", "numpy", "Pillow"]


def _compute_depskey() -> str:
    parts = []
    for pkg in sorted(_DEP_PACKAGES):
        try:
            parts.append(f"{pkg}=={md.version(pkg)}")
        except md.PackageNotFoundError:
            parts.append(f"{pkg}==?")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def _is_deps(rel: Path) -> bool:
    parts = rel.parts
    return len(parts) >= 2 and parts[0] == "_internal" and parts[1] in DEPS_INTERNAL_DIRS


def _zip_files(zip_path: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in files:
            zf.write(f, f.relative_to(DIST).as_posix())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 64), b""):
            h.update(block)
    return h.hexdigest()


def _asset_entry(path: Path) -> dict:
    return {"name": path.name, "size": path.stat().st_size, "sha256": _sha256(path)}


def main() -> int:
    if not DIST.is_dir():
        print(f"Missing dist folder: {DIST}", file=sys.stderr)
        return 1

    depskey = _compute_depskey()
    app_files: list[Path] = []
    deps_files: list[Path] = []
    for path in DIST.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(DIST)
        (deps_files if _is_deps(rel) else app_files).append(path)

    app_zip = OUT / f"pygiffer-app-{__version__}-windows.zip"
    deps_zip = OUT / f"pygiffer-deps-{depskey}-windows.zip"

    print(f"version={__version__}  depskey={depskey}")
    print(f"app files: {len(app_files)}  deps files: {len(deps_files)}")

    _zip_files(app_zip, app_files)
    _zip_files(deps_zip, deps_files)

    manifest = {
        "schema": 1,
        "version": __version__,
        "depskey": depskey,
        "app": _asset_entry(app_zip),
        "deps": _asset_entry(deps_zip),
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote {app_zip.name} ({app_zip.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {deps_zip.name} ({deps_zip.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
