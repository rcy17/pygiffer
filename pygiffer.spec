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
]

# Unused Qt submodules trimmed from the GUI build. We keep QtCore/QtGui/QtWidgets;
# never list the bare "PyQt6" here or the whole package gets excluded.
QT_UNUSED_EXCLUDES = [
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

GUI_EXCLUDES = COMMON_EXCLUDES + QT_UNUSED_EXCLUDES + ["cv2", "PIL", "numpy"]
# CLI must never bundle PyQt6 at all.
CLI_EXCLUDES = COMMON_EXCLUDES + ["PyQt6"]

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


# Qt DLLs are collected by PyInstaller's standard PyQt6 hook into
# PyQt6\Qt6\bin and made discoverable by the runtime hook below, so we do NOT
# copy them flat into PyQt6\ (that just doubled the package size).
gui_runtime_hooks = ["runtime/pyi_rth_qt_path.py"]
cli_runtime_hooks = ["runtime/pyi_rth_cli_path.py"]
gui_binaries = conda_runtime_binaries()
cli_binaries = conda_runtime_binaries() + cv2_binaries


# Qt modules / helper DLLs we never use. Filtering them out of the GUI build
# shrinks PyQt6\ dramatically (we only need QtCore/QtGui/QtWidgets).
_QT_DROP_NAME_TOKENS = (
    "qt6quick", "qt6qml", "qt63d", "qt6quick3d",
    "qt6multimedia", "qt6spatialaudio",
    "qt6pdf", "qt6designer", "qt6test", "qt6sql",
    "qt6shadertools", "qt6charts", "qt6datavisualization",
    "qt6network", "qt6bluetooth", "qt6nfc", "qt6positioning",
    "qt6sensors", "qt6serialport", "qt6websockets", "qt6webchannel",
    "qt6virtualkeyboard", "qt6texttospeech", "qt6remoteobjects",
    "qt6labs", "qt6help", "qt6concurrent",
    "opengl32sw", "d3dcompiler",
    "avcodec", "avformat", "avutil", "swscale", "swresample",
    # conda's ICU (versioned _58 symbols) is auto-pulled by PyInstaller but is
    # incompatible with this Qt build, which needs the unversioned ICU exports
    # provided by Windows' own System32\icuuc.dll. Drop it so the OS copy wins.
    "icuuc", "icudt", "icuin", "icuio", "icutu",
)
_QT_DROP_PATH_TOKENS = (
    "qt6/translations",
    "qt6/qml",
    "plugins/multimedia",
    "plugins/qmltooling",
    "plugins/scenegraph",
    "plugins/sqldrivers",
    "plugins/generic",
    "plugins/networkinformation",
    "plugins/tls",
)


def _keep_gui_entry(dest: str) -> bool:
    low = dest.replace("\\", "/").lower()
    if any(tok in low for tok in _QT_DROP_PATH_TOKENS):
        return False
    base = low.rsplit("/", 1)[-1]
    return not any(tok in base for tok in _QT_DROP_NAME_TOKENS)


def prune_qt(analysis) -> None:
    analysis.binaries = [e for e in analysis.binaries if _keep_gui_entry(e[0])]
    analysis.datas = [e for e in analysis.datas if _keep_gui_entry(e[0])]

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

prune_qt(a_gui)

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
