"""Generate window and taskbar icon assets from gifs/馒头.gif."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC_GIF = ROOT / "gifs" / "馒头.gif"
ASSETS = ROOT / "assets"

# Title bar / EXE embed — fewer sizes, larger master downscale chain.
APP_ICO_SIZES = (16, 32, 48, 256)

# Taskbar (incl. per-monitor DPI) — more sizes, sharpened when tiny.
TASKBAR_ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

MASTER_PX = 512


def _first_frame(path: Path) -> Image.Image:
    with Image.open(path) as img:
        img.seek(0)
        return img.convert("RGBA")


def _master_canvas(frame: Image.Image) -> Image.Image:
    w, h = frame.size
    scale = MASTER_PX / max(w, h)
    if scale <= 1.0:
        return frame
    size = (int(round(w * scale)), int(round(h * scale)))
    return frame.resize(size, Image.Resampling.LANCZOS)


def _render_icon(master: Image.Image, size: int, sharpen_small: bool) -> Image.Image:
    icon = master.resize((size, size), Image.Resampling.LANCZOS)
    if sharpen_small and size <= 48:
        icon = icon.filter(ImageFilter.UnsharpMask(radius=0.8, percent=150, threshold=1))
    return icon


def _save_ico(path: Path, images: list[Image.Image], sizes: tuple[int, ...]) -> None:
    # Pillow writes every size only when the largest image is saved first.
    pairs = sorted(zip(sizes, images, strict=True), key=lambda item: item[0], reverse=True)
    ordered_sizes = [(size, size) for size, _ in pairs]
    ordered_images = [image for _, image in pairs]
    ordered_images[0].save(
        path,
        format="ICO",
        sizes=ordered_sizes,
        append_images=ordered_images[1:],
    )


def main() -> int:
    if not SRC_GIF.exists():
        raise SystemExit(f"Source GIF not found: {SRC_GIF}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    master = _master_canvas(_first_frame(SRC_GIF))

    app_icons = [_render_icon(master, size, sharpen_small=False) for size in APP_ICO_SIZES]
    taskbar_icons = [_render_icon(master, size, sharpen_small=True) for size in TASKBAR_ICO_SIZES]

    app_path = ASSETS / "app.ico"
    taskbar_path = ASSETS / "taskbar.ico"
    _save_ico(app_path, app_icons, APP_ICO_SIZES)
    _save_ico(taskbar_path, taskbar_icons, TASKBAR_ICO_SIZES)

    print(f"Wrote {app_path} ({', '.join(map(str, APP_ICO_SIZES))})")
    print(f"Wrote {taskbar_path} ({', '.join(map(str, TASKBAR_ICO_SIZES))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
