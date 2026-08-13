"""Render quality sit and stand previews for the selected male_01 character.

This renderer is intentionally local and self-contained: it reuses the existing
provider compositing/encoding helpers but never calls the shared video provider
or changes any of its files.  The authored sit and stand sheets stay grounded
through bottom-aligned pose blends, while the background and character root are
locked to make the action easy to read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
BACKEND = next(
    path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file()
)
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    _blend_bottom_aligned,
    _fit_background,
    _load_video_dependencies,
    _optical_flow_interpolate,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
)


CHARACTER = "male_01"
FPS = 24
WIDTH = 768
HEIGHT = 384
DURATION = 4.5
EXPECTED_CELLS = 8

CHARACTER_REFERENCE = ROOT / "assets" / "characters" / f"{CHARACTER}_reference_v2.png"
SIT_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / f"{CHARACTER}_sit_cycle_v1.png"
STAND_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / f"{CHARACTER}_stand_cycle_v1.png"
BACKGROUND = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
OUTPUT_DIR = ROOT / "output" / "video_previews"
SIT_OUTPUT = OUTPUT_DIR / f"{CHARACTER}_sit_quality_v2.mp4"
STAND_OUTPUT = OUTPUT_DIR / f"{CHARACTER}_stand_quality_v2.mp4"
CONTACT_OUTPUT = OUTPUT_DIR / f"{CHARACTER}_sit_stand_quality_v2_contact.png"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("sit", "stand", "all"), default="all")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    parser.add_argument("--duration", type=float, default=DURATION)
    return parser.parse_args()


def _smoothstep(amount: float) -> float:
    value = min(max(float(amount), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def _load_cells(Image):
    for path in (CHARACTER_REFERENCE, SIT_SHEET, STAND_SHEET, BACKGROUND):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required asset: {path}")

    reference = Image.open(CHARACTER_REFERENCE).convert("RGBA")
    if reference.getchannel("A").getbbox() is None:
        raise ValueError(f"Reference has no visible pixels: {CHARACTER_REFERENCE}")

    sheets = {}
    for name, path in (("sit", SIT_SHEET), ("stand", STAND_SHEET)):
        sheet = Image.open(path).convert("RGBA")
        cells = _prepare_motion_sheet(sheet, Image)
        if len(cells) != EXPECTED_CELLS:
            raise ValueError(f"Expected {EXPECTED_CELLS} {name} cells, got {len(cells)}")
        if sheet.getchannel("A").getbbox() is None:
            raise ValueError(f"Motion sheet is empty: {path}")
        sheets[name] = cells
    return reference, sheets, Image.open(BACKGROUND).convert("RGBA")


def _pose_at(keyframes, progress: float, cells, Image, cv2, np, cache: dict):
    """Blend between absolute pose keyframes with short, stable boundary holds."""
    value = min(max(float(progress), 0.0), 1.0)
    if value <= keyframes[0][0]:
        name, index = keyframes[0][1]
        return cells[name][index]
    for (start, first), (end, second) in zip(keyframes, keyframes[1:]):
        if value > end:
            continue
        if first == second or end <= start:
            name, index = first
            return cells[name][index]
        local = _smoothstep((value - start) / (end - start))
        cache_key = (first, second, round(local, 3))
        if cache_key not in cache:
            first_image = cells[first[0]][first[1]]
            second_image = cells[second[0]][second[1]]
            cache[cache_key] = _optical_flow_interpolate(
                first_image,
                second_image,
                local,
                Image=Image,
                cv2=cv2,
                np=np,
                cache=cache,
                cache_key=("quality-flow", first, second),
            )
        return cache[cache_key]
    name, index = keyframes[-1][1]
    return cells[name][index]


def _keyframes(action: str):
    if action == "sit":
        # Preparation is held briefly, then the seated pose gets the longest hold.
        return (
            (0.00, ("sit", 0)),
            (0.11, ("sit", 0)),
            (0.25, ("sit", 1)),
            (0.40, ("sit", 2)),
            (0.55, ("sit", 3)),
            (0.68, ("sit", 4)),
            (1.00, ("sit", 4)),
        )
    # Start from a seated hold, transfer into the authored low stand pose, and
    # leave enough time at the end for a clearly readable upright hold.
    return (
        (0.00, ("sit", 4)),
        (0.10, ("sit", 4)),
        (0.22, ("stand", 0)),
        (0.34, ("stand", 1)),
        (0.48, ("stand", 3)),
        (0.61, ("stand", 5)),
        (0.73, ("stand", 7)),
        (1.00, ("stand", 7)),
    )


def _render_video(
    *,
    action: str,
    output: Path,
    fps: int,
    width: int,
    height: int,
    duration: float,
    dependencies,
    cv2,
    reference,
    cells,
    background,
) -> dict:
    imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps = dependencies
    total_frames = max(2, round(duration * fps))
    cache = {}
    keyframes = _keyframes(action)

    # A single fitted background is reused for all frames; this keeps the scene
    # pixel-stable so only the character motion can attract attention.
    plan = {
        "action": "idle",
        "target": "scene",
        "background_key": "fantasy_castle",
        "motion_focus": "character",
        "camera_motion": "locked",
    }
    locked_background = _fit_background(
        background, Image, ImageOps, width, height, 0.0, plan
    )
    center_x = width * 0.46
    ground_y = height * 0.92
    scale = 0.66

    def frames() -> Iterable:
        for frame_index in range(total_frames):
            progress = frame_index / max(total_frames - 1, 1)
            frame = locked_background.copy()
            pose = _pose_at(keyframes, progress, cells, Image, cv2, np, cache)
            _paste_character_layer(
                frame=frame,
                character_image=pose,
                Image=Image,
                ImageDraw=ImageDraw,
                ImageFilter=ImageFilter,
                center_x=center_x,
                ground_y=ground_y,
                scale=scale,
                rotation=0.0,
                ground_contact=1.0,
            )
            yield ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015)

    output.parent.mkdir(parents=True, exist_ok=True)
    video_bytes = _write_video_frames(
        output_path=output,
        frame_rate=fps,
        frames=frames(),
        imageio=imageio,
        np=np,
    )
    return {
        "action": action,
        "character": CHARACTER,
        "output": str(output),
        "duration_seconds": duration,
        "fps": fps,
        "frame_count": total_frames,
        "resolution": [width, height],
        "codec": "H.264/libx264",
        "motion_phases": (
            ["standing_hold", "lowering", "seated_settle", "seated_hold"]
            if action == "sit"
            else ["seated_hold", "weight_transfer", "extension", "upright_hold"]
        ),
        "grounding": "bottom_aligned_pose_blends_fixed_ground_y",
        "camera": "locked_background_and_fixed_character_root",
        "bytes": len(video_bytes),
        "source_assets": [str(CHARACTER_REFERENCE), str(SIT_SHEET), str(STAND_SHEET)],
    }


def _write_contact_sheet(video_paths, output: Path, fps: int, Image, ImageDraw, imageio):
    samples = 9
    columns = 3
    thumb_w = 256
    label_h = 30
    rows_per_video = (samples + columns - 1) // columns
    source_frames = []
    for action, path in video_paths:
        reader = imageio.get_reader(str(path))
        try:
            count = reader.count_frames()
            frames = []
            for sample in range(samples):
                index = round(sample * (count - 1) / (samples - 1))
                frames.append((index, Image.fromarray(reader.get_data(index)).convert("RGB")))
        finally:
            reader.close()
        source_frames.append((action, frames))

    first = source_frames[0][1][0][1]
    thumb_h = round(thumb_w * first.height / first.width)
    title_h = 38
    sheet = Image.new(
        "RGB",
        (columns * thumb_w, title_h + len(source_frames) * rows_per_video * (thumb_h + label_h)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    y_offset = 0
    for action, frames in source_frames:
        draw.text((8, y_offset + 10), f"male_01 {action.upper()} quality v2", fill="black")
        y_offset += title_h
        for sample, (index, frame) in enumerate(frames):
            frame.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = (sample % columns) * thumb_w
            y = y_offset + (sample // columns) * (thumb_h + label_h)
            sheet.paste(frame, (x, y + label_h))
            draw.text((x + 8, y + 7), f"{index / fps:04.1f}s / frame {index}", fill="black")
        y_offset += rows_per_video * (thumb_h + label_h)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main(args: argparse.Namespace) -> None:
    dependencies = _load_video_dependencies()
    imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps = dependencies
    try:
        import cv2
    except ImportError:
        cv2 = None
    reference, sheets, background = _load_cells(Image)
    fps = min(max(int(args.fps), 12), 30)
    width = max(256, int(args.width))
    height = max(128, int(args.height))
    duration = max(2.0, float(args.duration))
    reports = []
    videos = []
    if args.only in ("sit", "all"):
        reports.append(_render_video(
            action="sit", output=SIT_OUTPUT, fps=fps, width=width, height=height,
            duration=duration, dependencies=dependencies, reference=reference,
            cv2=cv2, cells=sheets, background=background,
        ))
        videos.append(("sit", SIT_OUTPUT))
    if args.only in ("stand", "all"):
        reports.append(_render_video(
            action="stand", output=STAND_OUTPUT, fps=fps, width=width, height=height,
            duration=duration, dependencies=dependencies, reference=reference,
            cv2=cv2, cells=sheets, background=background,
        ))
        videos.append(("stand", STAND_OUTPUT))
    _write_contact_sheet(videos, CONTACT_OUTPUT, fps, Image, ImageDraw, imageio)
    result = {"reports": reports, "contact_sheet": str(CONTACT_OUTPUT)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(_parse_args())
