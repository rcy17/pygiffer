"""Ensure bundled Qt6 and Python DLL directories are visible to extension modules."""


def _pyi_rthook():
    import os
    import sys

    if not sys.platform.startswith("win") or not hasattr(sys, "_MEIPASS"):
        return

    os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ.get("PATH", "")

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(sys._MEIPASS)
        qt_bin = os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "bin")
        if os.path.isdir(qt_bin):
            os.environ["PATH"] = qt_bin + os.pathsep + os.environ["PATH"]
            os.add_dll_directory(qt_bin)

        plugins = os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "plugins")
        if os.path.isdir(plugins):
            os.add_dll_directory(plugins)


_pyi_rthook()
del _pyi_rthook
