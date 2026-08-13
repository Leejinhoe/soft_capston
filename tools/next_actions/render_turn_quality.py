"""Render a fixed-camera male_01 turn-in-place quality prototype.

The repository has no dedicated turn sheet. This renderer deliberately audits
that gap, then uses the strongest existing front, three-quarter, and rear
anchors to make a stable prototype without changing the shared provider.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
CHARACTER_KEY = "male_01"
ASSET_DIR = ROOT / "assets"
CHARACTER_DIR = ASSET_DIR / "characters"
SHEET_DIR = CHARACTER_DIR / "motion_sheets"
BACKGROUND_PATH = ASSET_DIR / "backgrounds" / "fantasy_castle_wide_v2.png"
OUTPUT_DIR = ROOT / "output" / "video_previews"
DEFAULT_OUTPUT = OUTPUT_DIR / "male_01_turn_quality_v1.mp4"
DEFAULT_CONTACT = OUTPUT_DIR / "male_01_turn_quality_v1_contact.png"
DEFAULT_REPORT = OUTPUT_DIR / "male_01_turn_quality_v1_report.json"

WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION = 7.0
GROUND_Y = 424
CENTER_X = 480
SHEET_COLUMNS = 4
SHEET_ROWS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--contact", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION)
    return parser.parse_args()


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 16)
    except OSError:
        return ImageFont.load_default()


def _extract_cell(path: Path, index: int) -> Image.Image:
    with Image.open(path) as source:
        source = source.convert("RGBA")
        column = index % SHEET_COLUMNS
        row = index // SHEET_COLUMNS
        left = round(column * source.width / SHEET_COLUMNS)
        right = round((column + 1) * source.width / SHEET_COLUMNS)
        top = round(row * source.height / SHEET_ROWS)
        bottom = round((row + 1) * source.height / SHEET_ROWS)
        cell = source.crop((left, top, right, bottom))
    bbox = cell.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"Empty sprite cell {index}: {path}")
    return cell.crop(bbox)


def _fit_pose(pose: Image.Image, *, target_height: int = 348) -> Image.Image:
    scale = target_height / max(1, pose.height)
    size = (max(1, round(pose.width * scale)), target_height)
    return pose.resize(size, Image.Resampling.LANCZOS)


def _fit_background(background: Image.Image) -> Image.Image:
    scale = max(WIDTH / background.width, HEIGHT / background.height)
    resized = background.resize(
        (round(background.width * scale), round(background.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - WIDTH) // 2)
    top = max(0, (resized.height - HEIGHT) // 2)
    return resized.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGBA")


def _ease(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def _blend_pose(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    """Blend equal-size, bottom-aligned poses only during short handoff windows."""

    first_canvas = Image.new("RGBA", second.size, (0, 0, 0, 0))
    second_canvas = Image.new("RGBA", second.size, (0, 0, 0, 0))
    first_canvas.alpha_composite(first, ((second.width - first.width) // 2, second.height - first.height))
    second_canvas.alpha_composite(second, (0, 0))
    return Image.blend(first_canvas, second_canvas, _ease(amount))


def _center_pose(pose: Image.Image, *, scale: float = 1.0) -> Image.Image:
    if scale == 1.0:
        return pose
    return pose.resize(
        (max(1, round(pose.width * scale)), max(1, round(pose.height * scale))),
        Image.Resampling.LANCZOS,
    )


def _draw_guides(frame: Image.Image, phase: str, *, font: ImageFont.ImageFont) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    draw.rectangle((16, 14, WIDTH - 16, 56), fill=(11, 22, 42, 180))
    draw.text((30, 27), "TURN IN PLACE  /  male_01", fill=(255, 255, 255, 245), font=font)
    draw.text((WIDTH - 250, 27), "FIXED CAMERA  FRONT -> BACK", fill=(232, 241, 255, 235), font=font)

    # Persistent screen-space guides make background drift and character sliding obvious.
    draw.line((CENTER_X, 74, CENTER_X, GROUND_Y + 3), fill=(255, 255, 255, 105), width=2)
    draw.line((80, GROUND_Y + 3, WIDTH - 80, GROUND_Y + 3), fill=(255, 255, 255, 115), width=2)
    draw.line((CENTER_X - 12, GROUND_Y - 8, CENTER_X + 12, GROUND_Y - 8), fill=(255, 242, 178, 210), width=2)
    draw.line((CENTER_X, GROUND_Y - 20, CENTER_X, GROUND_Y + 4), fill=(255, 242, 178, 210), width=2)
    draw.text((42, GROUND_Y + 12), "LEFT", fill=(255, 255, 255, 200), font=font)
    draw.text((WIDTH - 90, GROUND_Y + 12), "RIGHT", fill=(255, 255, 255, 200), font=font)

    badge_width = draw.textbbox((0, 0), phase, font=font)[2] + 28
    draw.rounded_rectangle((CENTER_X - badge_width // 2, 68, CENTER_X + badge_width // 2, 96), radius=6, fill=(11, 22, 42, 190))
    draw.text((CENTER_X - badge_width // 2 + 14, 76), phase, fill=(255, 242, 178, 245), font=font)


def _draw_character(frame: Image.Image, pose: Image.Image, *, shadow_width: int = 150) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    draw.ellipse(
        (CENTER_X - shadow_width // 2, GROUND_Y - 5, CENTER_X + shadow_width // 2, GROUND_Y + 11),
        fill=(20, 24, 31, 95),
    )
    x = CENTER_X - pose.width // 2
    y = GROUND_Y - pose.height
    frame.alpha_composite(pose, (x, y))


def _phase_at(seconds: float) -> tuple[str, float]:
    phases = (
        ("FRONT HOLD", 0.0, 1.05),
        ("PIVOT", 1.05, 2.05),
        ("PELVIS + TORSO", 2.05, 3.35),
        ("GAZE LEADS", 3.35, 4.45),
        ("BACK HOLD", 4.45, DURATION),
    )
    for name, start, end in phases:
        if seconds < end:
            return name, (seconds - start) / max(0.001, end - start)
    return phases[-1][0], 1.0


def _pose_at(seconds: float, poses: dict[str, Image.Image]) -> Image.Image:
    phase, local = _phase_at(seconds)
    if phase == "FRONT HOLD":
        return poses["front"]
    if phase == "PIVOT":
        # Hold the planted front stance, then reveal a grounded three-quarter anchor.
        if local < 0.32:
            return poses["front"]
        return _blend_pose(poses["front"], poses["three_quarter"], (local - 0.32) / 0.68)
    if phase == "PELVIS + TORSO":
        return poses["three_quarter"]
    if phase == "GAZE LEADS":
        if local < 0.28:
            return poses["three_quarter_gaze"]
        return _blend_pose(poses["three_quarter_gaze"], poses["rear"], (local - 0.28) / 0.72)
    return poses["rear"]


def _load_assets() -> tuple[dict[str, Image.Image], dict[str, object]]:
    paths = {
        "front": SHEET_DIR / f"{CHARACTER_KEY}_stand_cycle_v1.png",
        "three_quarter": SHEET_DIR / f"{CHARACTER_KEY}_interaction_cycle_v22.png",
        "three_quarter_gaze": SHEET_DIR / f"{CHARACTER_KEY}_interaction_cycle_v22.png",
        "rear": SHEET_DIR / f"{CHARACTER_KEY}_target_journey_sheet_v4.png",
    }
    required = [BACKGROUND_PATH, *paths.values()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required assets:\n" + "\n".join(missing))

    raw = {
        "front": _extract_cell(paths["front"], 7),
        "three_quarter": _extract_cell(paths["three_quarter"], 0),
        "three_quarter_gaze": _extract_cell(paths["three_quarter_gaze"], 2),
        "rear": _extract_cell(paths["rear"], 0),
    }
    poses = {name: _fit_pose(pose) for name, pose in raw.items()}
    audit = {
        "character": CHARACTER_KEY,
        "dedicated_turn_sheet": None,
        "dedicated_turn_sheet_found": False,
        "usable_direction_anchors": {
            "front_standing": str(paths["front"]),
            "three_quarter_standing": str(paths["three_quarter"]),
            "rear_running": str(paths["rear"]),
        },
        "rotation_asset_status": "partial_not_sufficient_for_final_turn",
        "prototype_policy": "fixed_camera_and_ground_anchor_with_front_three_quarter_rear_handoff",
        "known_limitations": [
            "No dedicated turn-in-place sheet was found.",
            "The rear anchor comes from a running sheet, so one rear foot is lifted.",
            "The pelvis-to-torso and gaze phases are represented by existing three-quarter anchors, not new rotation art.",
        ],
    }
    return poses, audit


def _render_frames(poses: dict[str, Image.Image], *, fps: int, duration: float) -> Iterable[Image.Image]:
    with Image.open(BACKGROUND_PATH) as source:
        background = _fit_background(source.convert("RGBA"))
    font = _font()
    total_frames = round(fps * duration)
    for index in range(total_frames):
        seconds = index / fps
        frame = background.copy()
        phase, _ = _phase_at(min(seconds, DURATION - 0.001))
        _draw_character(frame, _pose_at(seconds, poses))
        _draw_guides(frame, phase, font=font)
        yield frame.convert("RGB")


def _write_contact_sheet(video: Path, output: Path, *, fps: int) -> None:
    reader = imageio.get_reader(str(video))
    try:
        count = reader.count_frames()
        samples = 14
        source = Image.fromarray(reader.get_data(0)).convert("RGB")
        thumb_width = 240
        thumb_height = round(thumb_width * source.height / source.width)
        label_height = 30
        columns = 4
        rows = (samples + columns - 1) // columns
        sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "white")
        draw = ImageDraw.Draw(sheet)
        font = _font()
        for index in range(samples):
            frame_index = round(index * max(0, count - 1) / max(1, samples - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            x = (index % columns) * thumb_width
            y = (index // columns) * (thumb_height + label_height)
            sheet.paste(frame, (x, y + label_height))
            phase, _ = _phase_at(frame_index / fps)
            draw.text((x + 8, y + 7), f"{frame_index / fps:04.1f}s  {phase}", fill="black", font=font)
    finally:
        reader.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _verify_video(path: Path, *, fps: int, duration: float) -> dict[str, object]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    measured_fps = float(metadata.get("fps") or 0.0)
    measured_size = tuple(metadata.get("size") or ())
    expected_frames = round(fps * duration)
    result = {
        "path": str(path.resolve()),
        "resolution": list(measured_size),
        "fps": measured_fps,
        "frame_count": frame_count,
        "expected_frame_count": expected_frames,
        "duration_seconds": round(frame_count / measured_fps, 3) if measured_fps else 0.0,
        "codec": metadata.get("codec", "unknown"),
    }
    if measured_size != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected video size: {result}")
    if frame_count != expected_frames:
        raise RuntimeError(f"Unexpected frame count: {result}")
    return result


def main() -> None:
    args = parse_args()
    fps = min(max(int(args.fps), 12), 30)
    duration = min(max(float(args.duration), 5.0), DURATION)
    poses, audit = _load_assets()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(args.output),
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    try:
        for frame in _render_frames(poses, fps=fps, duration=duration):
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()

    verification = _verify_video(args.output, fps=fps, duration=duration)
    _write_contact_sheet(args.output, args.contact, fps=fps)
    report = {
        "status": "prototype_asset_insufficient",
        "rendered_output": str(args.output.resolve()),
        "contact_sheet": str(args.contact.resolve()),
        "quality_targets": {
            "action_readability": "phase labels and fixed direction anchors are explicit",
            "character_identity": "male_01 assets only",
            "grounding": "fixed ground_y and shadow; rear source remains a running pose",
            "camera_stability": "fixed background crop, center guide, and locked character x",
        },
        "audit": audit,
        "verification": verification,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
