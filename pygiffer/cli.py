"""Unified CLI for convert / merge operations (no PyQt dependency)."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from pygiffer.convert import convert_to_gif
from pygiffer.merge import merge_gifs_horizontally
from pygiffer.utils import format_timestamp, notify_user

# Explorer launches the verb once per selected file (Document model), so each
# instance only receives a single %1. We aggregate the paths through a shared
# batch file and let a single "winner" instance perform the actual merge.
# The window must exceed the largest gap between two consecutive appends
# (instances launch almost simultaneously, so this only covers cold-start
# jitter). Both values are overridable via env vars for tuning without rebuild.
def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


_BATCH_WINDOW = _env_float("PYGIFFER_BATCH_WINDOW", 0.2)
_BATCH_POLL = _env_float("PYGIFFER_BATCH_POLL", 0.05)


def _collect_gif_paths(paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw.strip().strip('"'))
        if path.suffix.lower() == ".gif" and path.exists():
            result.append(path.resolve())
    return result


def _default_output_dir(paths: list[Path]) -> Path:
    parents = {path.parent.resolve() for path in paths}
    if len(parents) == 1:
        return next(iter(parents))
    return paths[0].parent.resolve()


def _batch_paths(flat: bool) -> tuple[Path, Path]:
    base = Path(tempfile.gettempdir())
    name = "pygiffer-merge-flat" if flat else "pygiffer-merge"
    return base / f"{name}.lst", base / f"{name}.lock"


def _with_lock(lock_dir: Path, timeout: float = 5.0):
    start = time.monotonic()
    while True:
        try:
            os.mkdir(lock_dir)
            return True
        except FileExistsError:
            if time.monotonic() - start > timeout:
                return False
            time.sleep(0.02)


def _release_lock(lock_dir: Path) -> None:
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass


def _append_batch(batch: Path, lock: Path, line: str) -> None:
    locked = _with_lock(lock)
    try:
        with open(batch, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    finally:
        if locked:
            _release_lock(lock)
    _debug_log(f"APPENDED (pid={os.getpid()}): {line}")


def _claim_batch(batch: Path) -> list[str] | None:
    """Wait until appends settle, then atomically claim the batch file.

    Returns the collected paths if this instance won the claim, else None.
    """
    while True:
        time.sleep(_BATCH_POLL)
        try:
            mtime = batch.stat().st_mtime
        except FileNotFoundError:
            return None
        if time.time() - mtime < _BATCH_WINDOW:
            continue
        claim = batch.with_suffix(".claim")
        try:
            os.replace(batch, claim)
        except (FileNotFoundError, PermissionError, OSError):
            return None
        try:
            lines = claim.read_text(encoding="utf-8").splitlines()
        finally:
            try:
                claim.unlink()
            except OSError:
                pass
        return [ln for ln in lines if ln.strip()]


def _cmd_merge_batch(args: argparse.Namespace) -> int:
    incoming = _collect_gif_paths(args.inputs)
    batch, lock = _batch_paths(args.flat)
    for path in incoming:
        _append_batch(batch, lock, str(path))

    collected = _claim_batch(batch)
    if collected is None:
        # Another instance owns the merge for this batch.
        return 0

    paths = _collect_gif_paths(collected)
    if len(paths) < 2:
        notify_user("PyGiffer", "请至少选择 2 个 GIF 文件", error=True, gui=args.notify)
        return 1

    output = _default_output_dir(paths) / f"{format_timestamp()}.gif"
    try:
        merge_gifs_horizontally(paths, output, remove_transparent=args.flat)
    except Exception as exc:
        notify_user("PyGiffer", f"合并失败:\n{exc}", error=True, gui=args.notify)
        return 1
    print(output)
    return 0


def _cmd_convert(args: argparse.Namespace) -> int:
    src = Path(args.input.strip().strip('"'))
    if not src.exists():
        notify_user("PyGiffer", f"文件不存在:\n{src}", error=True, gui=args.notify)
        return 1

    if args.output:
        output = Path(args.output)
    else:
        output = src.parent / f"{src.stem}-{format_timestamp()}.gif"
    try:
        convert_to_gif(src, output)
    except Exception as exc:
        notify_user("PyGiffer", f"转换失败:\n{exc}", error=True, gui=args.notify)
        return 1

    print(output)
    return 0


def _cmd_merge(args: argparse.Namespace) -> int:
    if getattr(args, "batch", False):
        return _cmd_merge_batch(args)

    paths = _collect_gif_paths(args.inputs)
    if len(paths) < 2:
        notify_user("PyGiffer", "请至少选择 2 个 GIF 文件", error=True, gui=args.notify)
        return 1

    if args.output:
        output = Path(args.output)
    else:
        output = _default_output_dir(paths) / f"{format_timestamp()}.gif"

    try:
        merge_gifs_horizontally(paths, output, remove_transparent=args.flat)
    except Exception as exc:
        notify_user("PyGiffer", f"合并失败:\n{exc}", error=True, gui=args.notify)
        return 1

    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pygiffer-cli", description="PyGiffer command-line tool")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Show native error message boxes (for Explorer context menu)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    convert_p = sub.add_parser("convert", help="Convert image/video to GIF")
    convert_p.add_argument("input", help="Source file path")
    convert_p.add_argument(
        "-o",
        "--output",
        help="Output GIF path (default: source dir / {stem}-{timestamp}.gif)",
    )
    convert_p.set_defaults(func=_cmd_convert)

    merge_p = sub.add_parser("merge", help="Merge GIF files horizontally")
    merge_p.add_argument("inputs", nargs="+", help="GIF file paths")
    merge_p.add_argument("-o", "--output", help="Output GIF path")
    merge_p.add_argument(
        "--flat",
        action="store_true",
        help="Fill transparent background with white",
    )
    merge_p.add_argument(
        "--batch",
        action="store_true",
        help="Aggregate per-file Explorer invocations into one merge",
    )
    merge_p.set_defaults(func=_cmd_merge)

    return parser


def _debug_log(message: str) -> None:
    import os
    import tempfile
    from datetime import datetime

    try:
        log_path = os.path.join(tempfile.gettempdir(), "pygiffer-cli.log")
        # %f is microseconds; trim to milliseconds for readability.
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {message}\n")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    _debug_log("ARGV: " + repr(raw))
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        result = args.func(args)
        _debug_log(f"EXIT: {result}")
        return result
    except SystemExit as exc:
        _debug_log(f"SYSTEMEXIT: {exc.code}")
        raise
    except Exception as exc:
        _debug_log(f"ERROR: {exc!r}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
