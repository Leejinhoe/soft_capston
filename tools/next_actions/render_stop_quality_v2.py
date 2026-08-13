"""Render a clean, grounded male_01 run-to-stop preview.

The final braking phase switches into the authored stand-cycle poses so the
character settles on both feet instead of freezing in a running pose.  Debug
markers are intentionally omitted from the delivery video.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_stop_quality as base  # noqa: E402


WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION = 8.0
GROUND_Y = 418
FINAL_X = 704
RUN_START_X = 126
RUN_BRAKE_X = 468
RUN_END_TIME = 2.35
BRAKE_END_TIME = 4.15
PLANT_END_TIME = 5.05

DEFAULT_VIDEO = ROOT / "output" / "video_previews" / "male_01_stop_quality_v2.mp4"
DEFAULT_CONTACT = ROOT / "output" / "video_previews" / "male_01_stop_quality_v2_contact.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION)
    return parser.parse_args()


def ease_out_cubic(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return 1.0 - (1.0 - value) ** 3


def ease_in_out(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def phase_for_time(second: float) -> str:
    if second < RUN_END_TIME:
        return "run"
    if second < BRAKE_END_TIME:
        return "brake"
    if second < PLANT_END_TIME:
        return "stand settle"
    return "stand hold"


def sprite_for_time(
    run_cells: list[Image.Image],
    stand_cells: list[Image.Image],
    second: float,
) -> Image.Image:
    if second < RUN_END_TIME:
        cycle = int(second * 9.0) % 8
        return run_cells[cycle]
    if second < BRAKE_END_TIME:
        local = (second - RUN_END_TIME) / (BRAKE_END_TIME - RUN_END_TIME)
        cycle = int((local * 2.8 + 0.1) * 8.0) % 8
        return run_cells[cycle]
    if second < PLANT_END_TIME:
        local = (second - BRAKE_END_TIME) / (PLANT_END_TIME - BRAKE_END_TIME)
        # The authored stand sheet moves from a low pose to a planted upright
        # pose, making the final action read as stopping rather than running.
        stand_sequence = (0, 1, 2, 3, 4, 5, 6, 7)
        index = min(int(ease_in_out(local) * len(stand_sequence)), len(stand_sequence) - 1)
        return stand_cells[stand_sequence[index]]
    return stand_cells[7]


def position_for_time(second: float) -> tuple[float, float]:
    if second < RUN_END_TIME:
        progress = second / RUN_END_TIME
        return RUN_START_X + (RUN_BRAKE_X - RUN_START_X) * progress, GROUND_Y
    if second < BRAKE_END_TIME:
        progress = (second - RUN_END_TIME) / (BRAKE_END_TIME - RUN_END_TIME)
        return RUN_BRAKE_X + (FINAL_X - RUN_BRAKE_X) * ease_out_cubic(progress), GROUND_Y
    return FINAL_X, GROUND_Y


def composite_clean(
    background: Image.Image,
    sprite: Image.Image,
    *,
    center_x: float,
    ground_y: float,
    second: float,
) -> Image.Image:
    frame = background.copy()
    draw = ImageDraw.Draw(frame, "RGBA")
    shadow_width = 112 if second < PLANT_END_TIME else 98
    draw.ellipse(
        (
            center_x - shadow_width / 2,
            ground_y - 7,
            center_x + shadow_width / 2,
            ground_y + 8,
        ),
        fill=(30, 38, 48, 96),
    )
    target_height = 252
    scale = target_height / max(1, sprite.height)
    target_width = max(1, round(sprite.width * scale))
    rendered = sprite.resize((target_width, target_height), Image.Resampling.LANCZOS)
    settle = 0.0
    if BRAKE_END_TIME <= second < PLANT_END_TIME:
        settle = 2.0 * (1.0 - ease_in_out((second - BRAKE_END_TIME) / 0.60))
    x = round(center_x - rendered.width / 2)
    y = round(ground_y - target_height - settle)
    frame.alpha_composite(rendered, (x, y))
    return frame.convert("RGB")


def build_frames(*, fps: int, duration: float) -> tuple[list[np.ndarray], list[str]]:
    background = base.make_background()
    run_cells = base.normalize_cells(base.load_cells(base.RUN_SHEET_PATH), target_height=252)
    stand_cells = base.normalize_cells(base.load_cells(base.STAND_SHEET_PATH), target_height=252)
    frames: list[np.ndarray] = []
    phases: list[str] = []
    for index in range(round(duration * fps)):
        second = index / fps
        sprite = sprite_for_time(run_cells, stand_cells, second)
        frame = composite_clean(
            background,
            sprite,
            center_x=position_for_time(second)[0],
            ground_y=GROUND_Y,
            second=second,
        )
        frames.append(np.asarray(frame, dtype=np.uint8))
        phases.append(phase_for_time(second))
    return frames, phases


def make_contact_sheet(path: Path, frames: list[np.ndarray], *, fps: int) -> None:
    sample_count = 16
    columns = 4
    frame_width = 320
    label_height = 34
    frame_height = round(frame_width * HEIGHT / WIDTH)
    rows = (sample_count + columns - 1) // columns
    sheet = Image.new("RGB", (columns * frame_width, rows * (frame_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for sample_index in range(sample_count):
        frame_index = min(round(sample_index * (len(frames) - 1) / (sample_count - 1)), len(frames) - 1)
        second = frame_index / fps
        x = (sample_index % columns) * frame_width
        y = (sample_index // columns) * (frame_height + label_height)
        tile = Image.fromarray(frames[frame_index]).resize((frame_width, frame_height), Image.Resampling.LANCZOS)
        sheet.paste(tile, (x, y + label_height))
        draw.rectangle((x, y, x + frame_width - 1, y + label_height - 1), fill=(244, 246, 249))
        draw.text((x + 8, y + 8), f"{second:0.2f}s  {phase_for_time(second)}", fill=(30, 38, 48), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)


def main() -> None:
    args = parse_args()
    fps = min(max(int(args.fps), 6), 30)
    duration = min(max(float(args.duration), 5.0), 15.0)
    frames, phases = build_frames(fps=fps, duration=duration)
    report = base.write_video(args.output, frames, fps=fps)
    make_contact_sheet(args.contact_sheet, frames, fps=fps)
    print(json.dumps({
        "video": report,
        "contact_sheet": str(args.contact_sheet.resolve()),
        "character": "male_01",
        "delivery": "clean_stop_with_authored_stand_settle",
        "phase_frame_counts": {phase: phases.count(phase) for phase in ("run", "brake", "stand settle", "stand hold")},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
