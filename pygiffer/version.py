"""Single source of truth for the application version.

The CI release workflow rewrites ``__version__`` from the pushed git tag
(e.g. tag ``v1.2.3`` -> ``1.2.3``) before building, so the packaged build
always reports the released version.
"""

from __future__ import annotations

__version__ = "0.1.2"


def version_tuple(value: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple of integers.

    Tolerates a leading ``v`` and pre-release/build suffixes (ignored).
    Non-numeric components are treated as 0 so comparison never crashes.
    """
    core = value.strip().lstrip("vV")
    for sep in ("-", "+"):
        if sep in core:
            core = core.split(sep, 1)[0]
    parts: list[int] = []
    for chunk in core.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    """Return True when ``candidate`` is a strictly newer version."""
    return version_tuple(candidate) > version_tuple(current)
