from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_WIDTH = 480
GIF_FPS = 12


def _resize_if_needed(img: Image.Image, max_width: int = MAX_WIDTH) -> Image.Image:
    if img.width <= max_width:
        return img
    ratio = max_width / img.width
    new_size = (max_width, max(1, int(img.height * ratio)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _load_image_frames(path: Path) -> tuple[list[Image.Image], list[int]]:
    img = Image.open(path)
    frames: list[Image.Image] = []
    delays: list[int] = []
    count = getattr(img, "n_frames", 1)
    for i in range(count):
        img.seek(i)
        frame = _resize_if_needed(img.convert("RGBA"))
        frames.append(frame)
        delays.append(int(img.info.get("duration", 100)))
    return frames, delays


def _save_gif(frames: list[Image.Image], delays: list[int], output: Path) -> None:
    if not frames:
        raise ValueError("no frames to save")

    rgb_frames = [f.convert("RGB") for f in frames]
    output.parent.mkdir(parents=True, exist_ok=True)
    rgb_frames[0].save(
        output,
        save_all=True,
        append_images=rgb_frames[1:],
        duration=delays,
        loop=0,
        optimize=True,
    )


def image_to_gif(input_path: Path, output_path: Path) -> Path:
    frames, delays = _load_image_frames(input_path)
    _save_gif(frames, delays, output_path)
    return output_path


def webp_to_gif(input_path: Path, output_path: Path | None = None) -> Path:
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_suffix(".gif")
    else:
        output_path = Path(output_path)
    image_to_gif(input_path, output_path)
    return output_path


def video_to_gif(input_path: Path, output_path: Path, fps: int = GIF_FPS) -> Path:
    import cv2

    input_path = Path(input_path)
    output_path = Path(output_path)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {input_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or fps
    step = max(1, round(src_fps / fps))
    frames: list[Image.Image] = []
    index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if index % step == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = _resize_if_needed(Image.fromarray(rgb))
            frames.append(pil.convert("RGBA"))
        index += 1

    cap.release()
    if not frames:
        raise ValueError(f"video has no frames: {input_path}")

    delay = int(1000 / fps)
    _save_gif(frames, [delay] * len(frames), output_path)
    return output_path


def convert_to_gif(input_path: Path, output_path: Path | None = None) -> Path:
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()

    if output_path is None:
        output_path = input_path.with_suffix(".gif")
    else:
        output_path = Path(output_path)

    if suffix in {".webp", ".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
        return image_to_gif(input_path, output_path)
    if suffix in {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v"}:
        return video_to_gif(input_path, output_path)
    raise ValueError(f"unsupported format: {suffix}")
