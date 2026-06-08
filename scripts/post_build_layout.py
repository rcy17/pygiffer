"""Post-process PyInstaller onedir output: move CLI EXE into _internal."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "pygiffer"
INTERNAL = DIST / "_internal"
CLI_EXE = "pygiffer-cli.exe"


def main() -> int:
    if not DIST.is_dir():
        print(f"Missing dist folder: {DIST}", file=sys.stderr)
        return 1
    if not INTERNAL.is_dir():
        print(f"Missing _internal folder: {INTERNAL}", file=sys.stderr)
        return 1

    src = DIST / CLI_EXE
    dst = INTERNAL / CLI_EXE
    if not src.exists():
        print(f"Missing CLI EXE: {src}", file=sys.stderr)
        return 1
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))
    print(f"Moved {CLI_EXE} -> _internal/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
