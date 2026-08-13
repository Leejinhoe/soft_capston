"""Render a standalone sitting action preview for male_01.

The motion sheet supplies the authored poses while the local provider helpers
handle background fitting, character placement, and H.264 encoding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    _blend_bottom_aligned,
    _character_motion_values,
    _fit_background,
    _load_video_dependencies,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
)


FPS = 24
WIDTH = 768
HEIGHT = 384
DURATION_SECONDS = 4.0
EXPECTED_CELLS = 8

CHARACTER_REFERENCE = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
MOTION_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_sit_cycle_v1.png"
BACKGROUND = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
DEFAULT_OUTPUT = ROOT / "output" / "video_previews" / "male_01_sit_v1.mp4"
DEFAULT_CONTACT = ROOT / "output" / "video_previews" / "male_01_sit_v1_contact.png"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--contact", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    return parser.parse_args()


def _pose_at(progress: float, cells, Image):
    """Read preparation, sit-down, hold, and recovery as one continuous action."""
    normalized = min(max(float(progress), 0.0), 1.0)
    # The authored sheet is: standing, lowering, kneeling/sitting, seated holds,
    # then recovery poses. Short holds make the action legible without a jump cut.
    timeline = (
        (0.00, 0),
        (0.10, 0),
        (0.23, 1),
        (0.38, 2),
        (0.48, 3),
        (0.70, 4),
        (0.78, 5),
        (0.88, 2),
        (0.96, 1),
        (1.00, 0),
    )
    if normalized >= 1.0:
        return cells[timeline[-1][1]]
    for index in range(len(timeline) - 1):
        start, first_index = timeline[index]
        end, second_index = timeline[index + 1]
        if normalized <= end:
            span = max(end - start, 1e-6)
            local = min(max((normalized - start) / span, 0.0), 1.0)
            # Keep the seated phase stable while blending the entry and exit.
            if first_index == second_index:
                return cells[first_index]
            return _blend_bottom_aligned(
                cells[first_index],
                cells[second_index],
                local * local * (3.0 - 2.0 * local),
                Image,
            )
    return cells[0]


def _write_contact_sheet(video_path: Path, contact_path: Path, fps: int, Image, ImageDraw, imageio):
    reader = imageio.get_reader(str(video_path))
    try:
        frame_count = reader.count_frames()
        samples = 9
        first = Image.fromarray(reader.get_data(0)).convert("RGB")
        thumb_w = 256
        thumb_h = round(thumb_w * first.height / first.width)
        label_h = 28
        columns = 3
        rows = (samples + columns - 1) // columns
        sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for sample in range(samples):
            frame_index = round(sample * (frame_count - 1) / (samples - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = (sample % columns) * thumb_w
            y = (sample // columns) * (thumb_h + label_h)
            sheet.paste(frame, (x, y + label_h))
            draw.text((x + 8, y + 7), f"{frame_index / fps:04.1f}s", fill="black")
    finally:
        reader.close()
    contact_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact_path)


def render(args: argparse.Namespace) -> dict:
    imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps = _load_video_dependencies()
    for path in (CHARACTER_REFERENCE, MOTION_SHEET, BACKGROUND):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required asset: {path}")

    reference = Image.open(CHARACTER_REFERENCE).convert("RGBA")
    sheet_image = Image.open(MOTION_SHEET).convert("RGBA")
    background = Image.open(BACKGROUND).convert("RGBA")
    if reference.getchannel("A").getbbox() is None:
        raise ValueError("male_01 reference has no visible pixels")
    cells = _prepare_motion_sheet(sheet_image, Image)
    if len(cells) != EXPECTED_CELLS:
        raise ValueError(f"Expected {EXPECTED_CELLS} motion cells, got {len(cells)}")

    fps = max(12, min(30, int(args.fps)))
    width = max(256, int(args.width))
    height = max(128, int(args.height))
    total_frames = round(DURATION_SECONDS * fps)
    motion_plan = {
        "action": "sit",
        "target": "scene",
        "background_key": "fantasy_castle",
        "motion_focus": "character",
        "camera_motion": "locked",
        "_duration_seconds": DURATION_SECONDS,
    }
    interpolation_cache = {}

    def frames():
        for index in range(total_frames):
            progress = index / max(total_frames - 1, 1)
            frame = _fit_background(
                background,
                Image,
                ImageOps,
                width,
                height,
                progress,
                motion_plan,
            )
            values = _character_motion_values(
                action="sit",
                progress=progress,
                width=width,
                height=height,
                motion_strength=2,
                motion_plan=motion_plan,
            )
            pose = _pose_at(progress, cells, Image)
            _paste_character_layer(
                frame=frame,
                character_image=pose,
                Image=Image,
                ImageDraw=ImageDraw,
                ImageFilter=ImageFilter,
                center_x=values["center_x"],
                ground_y=values["ground_y"] + values.get("bob", 0.0),
                scale=values["scale"],
                rotation=values["rotation"],
                ground_contact=values.get("ground_contact", 1.0),
            )
            yield ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    video_bytes = _write_video_frames(
        output_path=args.output,
        frame_rate=fps,
        frames=frames(),
        imageio=imageio,
        np=np,
    )
    _write_contact_sheet(args.output, args.contact, fps, Image, ImageDraw, imageio)
    metadata = {
        "character_reference": str(CHARACTER_REFERENCE),
        "motion_sheet": str(MOTION_SHEET),
        "background": str(BACKGROUND),
        "output": str(args.output),
        "contact_sheet": str(args.contact),
        "duration_seconds": DURATION_SECONDS,
        "fps": fps,
        "frame_count": total_frames,
        "resolution": [width, height],
        "codec": "H.264/libx264",
        "motion_phases": ["preparation", "sit_down", "seated_hold", "recovery"],
        "motion_cells": len(cells),
        "bytes": len(video_bytes),
    }
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return metadata


if __name__ == "__main__":
    render(_parse_args())
