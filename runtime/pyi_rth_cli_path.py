"""Add bundled DLL search paths for the CLI executable."""

from __future__ import annotations


def _pyi_rthook() -> None:
    import os
    import sys

    if not sys.platform.startswith("win") or not hasattr(sys, "_MEIPASS"):
        return

    base = sys._MEIPASS
    os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(base)
        cv2_dir = os.path.join(base, "cv2")
        if os.path.isdir(cv2_dir):
            os.add_dll_directory(cv2_dir)


_pyi_rthook()
del _pyi_rthook
