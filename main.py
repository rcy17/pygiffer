import os
import sys
from pathlib import Path


def _prepare_windows_dll_paths() -> None:
    if not sys.platform.startswith("win"):
        return

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent

    candidates = [
        base,
        base / "PyQt6",
        base / "PyQt6" / "Qt6" / "bin",
    ]
    path_parts = []
    for folder in candidates:
        if folder.is_dir():
            path_parts.append(str(folder))
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(folder))
    if path_parts:
        os.environ["PATH"] = os.pathsep.join(path_parts + [os.environ.get("PATH", "")])


_prepare_windows_dll_paths()

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from pygiffer.paths import taskbar_icon_path
from pygiffer.ui.main_window import MainWindow
from pygiffer.ui.theme import app_font, global_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PyGiffer")
    app.setApplicationDisplayName("PyGiffer")
    app.setFont(app_font())
    app.setStyleSheet(global_stylesheet())

    icon_file = taskbar_icon_path()
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
