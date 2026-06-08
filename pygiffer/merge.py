from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class GifClip:
    frames: list[Image.Image]
    delays: list[int]


def load_gif(path: Path) -> GifClip:
    img = Image.open(path)
    frames: list[Image.Image] = []
    delays: list[int] = []
    count = getattr(img, "n_frames", 1)
    for i in range(count):
        img.seek(i)
        frames.append(img.convert("RGBA"))
        delays.append(int(img.info.get("duration", 100)))
    if not frames:
        raise ValueError(f"empty gif: {path}")
    return GifClip(frames=frames, delays=delays)


def _scale_frame(frame: Image.Image, target_height: int) -> Image.Image:
    if frame.height == target_height:
        return frame
    new_width = max(1, int(frame.width * target_height / frame.height))
    return frame.resize((new_width, target_height), Image.Resampling.LANCZOS)


def _flatten_white(frame: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", frame.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, frame)


def merge_gifs_horizontally(
    input_paths: list[Path],
    output_path: Path,
    remove_transparent: bool = False,
) -> Path:
    if len(input_paths) < 2:
        raise ValueError("at least 2 GIF files required")

    clips = [load_gif(Path(p)) for p in input_paths]
    target_height = min(min(f.height for f in clip.frames) for clip in clips)
    max_frames = max(len(clip.frames) for clip in clips)

    scaled_clips: list[list[Image.Image]] = []
    for clip in clips:
        scaled: list[Image.Image] = []
        for frame in clip.frames:
            item = _scale_frame(frame, target_height)
            if remove_transparent:
                item = _flatten_white(item)
            scaled.append(item)
        scaled_clips.append(scaled)

    merged_frames: list[Image.Image] = []
    merged_delays: list[int] = []

    for frame_idx in range(max_frames):
        row_parts: list[Image.Image] = []
        delay = 0
        for clip_idx, clip in enumerate(clips):
            src_idx = min(frame_idx, len(scaled_clips[clip_idx]) - 1)
            row_parts.append(scaled_clips[clip_idx][src_idx])
            src_delay_idx = min(frame_idx, len(clip.delays) - 1)
            delay = max(delay, clip.delays[src_delay_idx])

        total_width = sum(part.width for part in row_parts)
        canvas = Image.new("RGBA", (total_width, target_height), (0, 0, 0, 0))
        x = 0
        for part in row_parts:
            canvas.paste(part, (x, 0))
            x += part.width

        if remove_transparent:
            canvas = canvas.convert("RGB")
        merged_frames.append(canvas)
        merged_delays.append(delay)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if remove_transparent:
        merged_frames[0].save(
            output_path,
            save_all=True,
            append_images=merged_frames[1:],
            duration=merged_delays,
            loop=0,
            optimize=True,
        )
    else:
        merged_frames[0].save(
            output_path,
            save_all=True,
            append_images=merged_frames[1:],
            duration=merged_delays,
            loop=0,
            disposal=2,
            optimize=True,
        )

    return output_path
