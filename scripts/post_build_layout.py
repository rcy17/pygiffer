"""Post-process PyInstaller onedir output.

1. Move the CLI EXE into _internal/.
2. Stage the registry helper scripts (root .bat launchers + _internal ps1).

Shared by both build_release.bat and the CI release workflow.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DIST = ROOT / "dist" / "pygiffer"
INTERNAL = DIST / "_internal"
CLI_EXE = "pygiffer-cli.exe"


def _move_cli() -> int:
    src = DIST / CLI_EXE
    dst = INTERNAL / CLI_EXE
    if not src.exists():
        # Already moved by a previous (incremental) run.
        if dst.exists():
            print(f"{CLI_EXE} already in _internal/")
            return 0
        print(f"Missing CLI EXE: {src}", file=sys.stderr)
        return 1
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))
    print(f"Moved {CLI_EXE} -> _internal/")
    return 0


def _stage_scripts() -> int:
    root_scripts = ["install_registry.bat", "uninstall_registry.bat"]
    for name in root_scripts:
        shutil.copy2(SCRIPTS / name, DIST / name)
    shutil.copy2(SCRIPTS / "install_registry.ps1", INTERNAL / "install_registry.ps1")
    print("Staged registry helper scripts.")
    return 0


def main() -> int:
    if not DIST.is_dir():
        print(f"Missing dist folder: {DIST}", file=sys.stderr)
        return 1
    if not INTERNAL.is_dir():
        print(f"Missing _internal folder: {INTERNAL}", file=sys.stderr)
        return 1

    rc = _move_cli()
    if rc != 0:
        return rc
    return _stage_scripts()


if __name__ == "__main__":
    raise SystemExit(main())
