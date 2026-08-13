"""Render a focused four-second climb action preview.

The renderer uses the authored 4x2 climb sheet as hard pose cuts. Each frame is
composited from a fresh background, so no character alpha or motion trail can
accumulate between frames.
"""

from __future__ import annotations

import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[3]
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
SHEET_PATH = (
    ROOT
    / "assets"
    / "characters"
    / "motion_sheets"
    / "male_01_climb_cycle_v1.png"
)
OUTPUT_PATH = ROOT / "output" / "video_previews" / "male_01_climb_v1.mp4"

WIDTH = 768
HEIGHT = 384
FPS = 24
DURATION = 4.0
FRAME_COUNT = round(FPS * DURATION)
SHEET_COLUMNS = 4
SHEET_ROWS = 2


def _load_poses() -> list[Image.Image]:
    sheet = Image.open(SHEET_PATH).convert("RGBA")
    cell_width = sheet.width // SHEET_COLUMNS
    cell_height = sheet.height // SHEET_ROWS
    if (cell_width * SHEET_COLUMNS, cell_height * SHEET_ROWS) != sheet.size:
        raise ValueError("The climb sheet must divide evenly into a 4x2 grid.")

    poses = []
    for row in range(SHEET_ROWS):
        for column in range(SHEET_COLUMNS):
            cell = sheet.crop(
                (
                    column * cell_width,
                    row * cell_height,
                    (column + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            )
            alpha_box = cell.getchannel("A").getbbox()
            if alpha_box is None:
                raise ValueError(f"Empty climb pose at index {len(poses)}")
            poses.append(cell.crop(alpha_box))
    if len(poses) != 8:
        raise ValueError(f"Expected 8 climb poses, found {len(poses)}")
    return poses


def _background() -> Image.Image:
    source = Image.open(BACKGROUND_PATH).convert("RGB")
    return ImageOps.fit(
        source,
        (WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.54, 0.52),
    ).convert("RGBA")


def _draw_opaque_stone_wall(frame: Image.Image) -> None:
    """Add one stable, opaque wall that gives the climb a clear target."""
    draw = ImageDraw.Draw(frame)
    left = 554
    right = 748
    top = 64
    wall = [
        (left + 16, HEIGHT),
        (left, top + 42),
        (left + 22, top + 4),
        (left + 74, top + 12),
        (left + 118, top),
        (right - 18, top + 16),
        (right, top + 56),
        (right - 8, HEIGHT),
    ]
    draw.polygon(wall, fill=(70, 77, 88, 255))
    draw.line(wall + [wall[0]], fill=(34, 40, 51, 255), width=4, joint="curve")

    for row in range(5):
        y = top + 54 + row * 58
        draw.line((left + 12, y, right - 14, y + 3), fill=(139, 147, 159, 255), width=2)
        offset = 16 if row % 2 else 0
        for column in range(3):
            x = left + 48 + column * 62 + offset
            draw.line((x, y - 53, x - 7, y), fill=(43, 50, 62, 255), width=2)


def _paste_pose(frame: Image.Image, pose: Image.Image, center_x: float, bottom_y: float) -> None:
    target_height = 142
    scale = target_height / pose.height
    target_size = (
        max(1, round(pose.width * scale)),
        max(1, round(pose.height * scale)),
    )
    rendered = pose.resize(target_size, Image.Resampling.LANCZOS)
    x = round(center_x - rendered.width / 2)
    y = round(bottom_y - rendered.height)
    frame.alpha_composite(rendered, (x, y))


def _smoothstep(progress: float) -> float:
    progress = max(0.0, min(1.0, progress))
    return progress * progress * (3.0 - 2.0 * progress)


def _frame_at(poses: list[Image.Image], index: int) -> Image.Image:
    seconds = index / FPS
    frame = _background()
    _draw_opaque_stone_wall(frame)

    approach_end = 0.95
    climb_end = 3.65
    if seconds < approach_end:
        progress = _smoothstep(seconds / approach_end)
        center_x = 128 + (493 - 128) * progress
        bottom_y = 335
        # Alternate two authored climbing poses to make the approach readable.
        pose = poses[6 if (index // 6) % 2 == 0 else 7]
    elif seconds < climb_end:
        progress = _smoothstep((seconds - approach_end) / (climb_end - approach_end))
        pose_index = min(7, int((seconds - approach_end) / (climb_end - approach_end) * 8))
        pose = poses[pose_index]
        center_x = 510 + 7 * progress
        # Keep the full character visible while still making the upward route clear.
        bottom_y = 332 - 165 * progress
    else:
        pose = poses[7]
        center_x = 517
        bottom_y = 170

    _paste_pose(frame, pose, center_x, bottom_y)
    return frame.convert("RGB")


def _write_video() -> dict:
    if not BACKGROUND_PATH.is_file():
        raise FileNotFoundError(BACKGROUND_PATH)
    if not SHEET_PATH.is_file():
        raise FileNotFoundError(SHEET_PATH)

    poses = _load_poses()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(OUTPUT_PATH),
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=2,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for index in range(FRAME_COUNT):
            writer.append_data(np.asarray(_frame_at(poses, index), dtype=np.uint8))
    finally:
        writer.close()

    reader = imageio.get_reader(str(OUTPUT_PATH))
    try:
        metadata = reader.get_meta_data()
        frame_count = reader.count_frames()
        first_frame = reader.get_data(0)
    finally:
        reader.close()

    result = {
        "output": str(OUTPUT_PATH),
        "duration_seconds": round(frame_count / FPS, 3),
        "fps": metadata.get("fps", FPS),
        "frame_count": frame_count,
        "resolution": [int(first_frame.shape[1]), int(first_frame.shape[0])],
        "codec": "H.264/libx264",
        "pose_count": len(poses),
        "background": str(BACKGROUND_PATH),
        "motion_sheet": str(SHEET_PATH),
    }
    if result["frame_count"] != FRAME_COUNT:
        raise RuntimeError(f"Unexpected frame count: {result['frame_count']}")
    if result["resolution"] != [WIDTH, HEIGHT]:
        raise RuntimeError(f"Unexpected resolution: {result['resolution']}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    _write_video()
