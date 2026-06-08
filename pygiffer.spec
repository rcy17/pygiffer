# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: GUI + CLI (no PyQt in CLI)."""

import sys
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE
from PyInstaller.building.build_main import MERGE, PYZ, Analysis
from PyInstaller.utils.hooks import collect_all

block_cipher = None

COMMON_EXCLUDES = [
    "tkinter",
    "_tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "notebook",
    "IPython",
    "PyQt6",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DRender",
    "PyQt6.QtCharts",
    "PyQt6.QtQuick",
    "PyQt6.QtQml",
    "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNetwork",
    "PyQt6.QtSql",
    "PyQt6.QtTest",
    "PyQt6.QtDesigner",
]

GUI_EXCLUDES = COMMON_EXCLUDES + ["cv2", "PIL", "numpy"]
CLI_EXCLUDES = [x for x in COMMON_EXCLUDES if not x.startswith("PyQt6")]

cv2_datas, cv2_binaries, cv2_hidden = collect_all("cv2")
CLI_HIDDEN = ["cv2", "PIL", "PIL._imaging", "numpy"] + cv2_hidden
GUI_HIDDEN = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
]


def _conda_search_roots() -> list[Path]:
    roots: list[Path] = [
        Path(sys.base_prefix) / "Library" / "bin",
        Path(sys.base_prefix) / "DLLs",
    ]
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("home ="):
                home = Path(line.split("=", 1)[1].strip())
                roots.extend([home / "Library" / "bin", home / "DLLs"])
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        deduped.append(root)
    return deduped


def conda_runtime_binaries() -> list[tuple[str, str]]:
    names = (
        "ffi.dll",
        "libcrypto-3-x64.dll",
        "libssl-3-x64.dll",
        "libexpat.dll",
        "zlib.dll",
        "sqlite3.dll",
    )
    binaries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for root in _conda_search_roots():
        if not root.is_dir():
            continue
        for name in names:
            path = root / name
            if path.exists() and name not in seen:
                binaries.append((str(path), "."))
                seen.add(name)
    return binaries


def qt_neighbor_binaries() -> list[tuple[str, str]]:
    import PyQt6

    qt_bin = Path(PyQt6.__file__).resolve().parent / "Qt6" / "bin"
    binaries: list[tuple[str, str]] = []
    if qt_bin.is_dir():
        for dll in sorted(qt_bin.glob("*.dll")):
            binaries.append((str(dll), "PyQt6"))
    return binaries


def python_neighbor_binaries() -> list[tuple[str, str]]:
    binaries: list[tuple[str, str]] = []
    for name in ("python3.dll", f"python{sys.version_info.major}{sys.version_info.minor}.dll"):
        path = Path(sys.base_prefix) / name
        if path.exists():
            binaries.append((str(path), "PyQt6"))
    return binaries


gui_runtime_hooks = ["runtime/pyi_rth_qt_path.py"]
cli_runtime_hooks = ["runtime/pyi_rth_cli_path.py"]
gui_binaries = conda_runtime_binaries() + qt_neighbor_binaries() + python_neighbor_binaries()
cli_binaries = conda_runtime_binaries() + cv2_binaries

a_gui = Analysis(
    ["main.py"],
    pathex=[],
    binaries=gui_binaries,
    datas=[("assets", "assets")],
    hiddenimports=GUI_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=gui_runtime_hooks,
    excludes=GUI_EXCLUDES,
    noarchive=False,
    optimize=0,
)
a_cli = Analysis(
    ["cli_main.py"],
    pathex=[],
    binaries=cli_binaries,
    datas=cv2_datas,
    hiddenimports=CLI_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=cli_runtime_hooks,
    excludes=CLI_EXCLUDES,
    noarchive=False,
    optimize=0,
)

MERGE((a_gui, "gui", "gui"), (a_cli, "cli", "cli"))

pyz_gui = PYZ(a_gui.pure, cipher=block_cipher)
pyz_cli = PYZ(a_cli.pure, cipher=block_cipher)

icon_path = "assets/app.ico"
gui_exe_kwargs = dict(
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    contents_directory="_internal",
)
cli_exe_kwargs = dict(gui_exe_kwargs, console=False, icon=icon_path, contents_directory=".")

exe_gui = EXE(pyz_gui, a_gui.scripts, [], name="pygiffer", **gui_exe_kwargs)
exe_cli = EXE(pyz_cli, a_cli.scripts, [], name="pygiffer-cli", **cli_exe_kwargs)

coll = COLLECT(
    exe_gui,
    exe_cli,
    a_gui.binaries,
    a_cli.binaries,
    a_gui.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pygiffer",
)
