"""Rewrite pygiffer/version.py __version__ from a git tag (CI use).

Usage: python scripts/set_version.py v1.2.3
Strips a leading 'v'. No-op-safe if the file format is unexpected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "pygiffer" / "version.py"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: set_version.py <tag>", file=sys.stderr)
        return 1

    version = sys.argv[1].strip().lstrip("vV")
    text = VERSION_FILE.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'^__version__\s*=\s*".*"',
        f'__version__ = "{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        print("Could not find __version__ assignment", file=sys.stderr)
        return 1
    VERSION_FILE.write_text(new_text, encoding="utf-8")
    print(f"Set __version__ = {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
