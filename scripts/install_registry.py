"""Install or remove PyGiffer Windows Explorer context menu entries."""

from __future__ import annotations

import argparse
import sys
import winreg
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "app.ico"


def _pythonw() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        candidate = exe.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def _convert_command() -> str:
    return f'"{_pythonw()}" -m pygiffer.cli --notify convert "%1"'


def _merge_command(*extra: str) -> str:
    # Explorer invokes once per file (%1); --batch aggregates them into one merge.
    parts = [
        f'"{_pythonw()}"',
        "-m",
        "pygiffer.cli",
        "--notify",
        "merge",
        *extra,
        "--batch",
        '"%1"',
    ]
    return " ".join(parts)


def _entries() -> list[tuple[str, str, str, bool, str]]:
    return [
        (
            r"SystemFileAssociations\.webp\shell\PyGifferWebpToGif",
            "转换为 gif 格式",
            _convert_command(),
            False,
            "",
        ),
        (
            r"SystemFileAssociations\.gif\shell\PyGifferMergeGifs",
            "合并为 gif",
            _merge_command(),
            True,
            "",
        ),
        (
            r"SystemFileAssociations\.gif\shell\PyGifferMergeGifsFlat",
            "合并为 gif （去除透明背景）",
            _merge_command("--flat"),
            True,
            "",
        ),
    ]


def install() -> None:
    cli = ROOT / "dist" / "pygiffer" / "_internal" / "pygiffer-cli.exe"
    icon = f"{cli.resolve()},0" if cli.exists() else (f"{ICON.resolve()},0" if ICON.exists() else "")
    for key_path, label, command, multi, applies_to in _entries():
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, label)
            if icon:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
            if applies_to:
                winreg.SetValueEx(key, "AppliesTo", 0, winreg.REG_SZ, applies_to)
            if multi:
                winreg.SetValueEx(key, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path + r"\command") as cmd_key:
            winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, command)
    print("PyGiffer 右键菜单已安装（开发模式）。")
    print(f"CLI: python -m pygiffer.cli")
    print("发布包请使用 scripts\\install_registry.bat。")


def uninstall() -> None:
    legacy = [
        r"*\shell\PyGifferMergeGifs",
        r"*\shell\PyGifferMergeGifsFlat",
        r"*\shell\PyGifferWebpToGif",
        r".webp\shell\PyGifferWebpToGif",
    ]
    for key_path in [entry[0] for entry in _entries()] + legacy:
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path + r"\command")
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path)
        except FileNotFoundError:
            pass
    print("PyGiffer 右键菜单已移除。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install PyGiffer context menu entries (dev)")
    parser.add_argument("action", choices=["install", "uninstall"])
    args = parser.parse_args()

    if args.action == "install":
        install()
    else:
        uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
