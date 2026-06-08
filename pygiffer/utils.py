from __future__ import annotations

from datetime import datetime
from pathlib import Path

IMAGE_EXTS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".bmp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v"}


def format_timestamp(when: datetime | None = None) -> str:
    when = when or datetime.now()
    return when.strftime("%m%d%H%M%S")


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def scan_gifs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    found: dict[str, Path] = {}
    for pattern in ("*.gif", "*.GIF"):
        for p in folder.rglob(pattern):
            if p.is_file():
                found[str(p.resolve())] = p.resolve()
    return sorted(found.values(), key=lambda p: p.name.lower())


def notify_user(title: str, message: str, error: bool = False, gui: bool = True) -> None:
    if not gui:
        return
    import ctypes

    # Keep dialogs above Explorer when launched from the context menu.
    flags = (0x10 if error else 0x40) | 0x00040000 | 0x00010000
    ctypes.windll.user32.MessageBoxW(0, message, title, flags)


def show_message(title: str, message: str, error: bool = False) -> None:
    notify_user(title, message, error=error, gui=True)
