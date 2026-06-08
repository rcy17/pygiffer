"""PyInstaller entry point for pygiffer-cli."""

from __future__ import annotations


def _notify_startup_error(message: str) -> None:
    try:
        import ctypes

        flags = 0x10 | 0x00040000 | 0x00010000
        ctypes.windll.user32.MessageBoxW(0, message, "PyGiffer", flags)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from pygiffer.cli import main

        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        _notify_startup_error(f"启动失败:\n{exc}")
        raise SystemExit(1) from exc
