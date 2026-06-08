from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return project_root() / "_internal"
    return project_root()


def asset_path(name: str) -> Path:
    return resource_root() / "assets" / name


def taskbar_icon_path() -> Path:
    taskbar = asset_path("taskbar.ico")
    if taskbar.exists():
        return taskbar
    return asset_path("app.ico")


def cli_executable() -> Path:
    if getattr(sys, "frozen", False):
        return project_root() / "_internal" / "pygiffer-cli.exe"
    return Path(sys.executable)


def cli_base_args() -> list[str]:
    if getattr(sys, "frozen", False):
        return []
    return ["-m", "pygiffer.cli"]


def cli_command(*args: str) -> tuple[str, list[str]]:
    return str(cli_executable()), cli_base_args() + list(args)
