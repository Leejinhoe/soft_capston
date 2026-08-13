"""Render a grounded male_01 run-to-stop quality preview.

This is intentionally a standalone preview renderer. It reuses the existing
male_01 run and stand sprite assets without changing the shared provider or
motion policy. The camera and ground anchor stay fixed so the stop can be
judged from the contact sheet as well as from the MP4.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "assets"
DEFAULT_VIDEO = ROOT / "output" / "video_previews" / "male_01_stop_quality_v1.mp4"
DEFAULT_CONTACT = (
    ROOT / "output" / "video_previews" / "male_01_stop_quality_v1_contact.png"
)

WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION = 8.0
GROUND_Y = 418
FINAL_X = 704
RUN_START_X = 126
RUN_BRAKE_X = 468
RUN_END_TIME = 2.35
BRAKE_END_TIME = 4.25
PLANT_END_TIME = 4.85

BACKGROUND_PATH = ASSET_DIR / "backgrounds" / "fantasy_castle_wide_v2.png"
RUN_SHEET_PATH = (
    ASSET_DIR / "characters" / "motion_sheets" / "male_01_run_cycle_v16.png"
)
STAND_SHEET_PATH = (
    ASSET_DIR / "characters" / "motion_sheets" / "male_01_stand_cycle_v1.png"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION)
    return parser.parse_args()


def validate_assets() -> None:
    for path in (BACKGROUND_PATH, RUN_SHEET_PATH, STAND_SHEET_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required asset was not found: {path}")


def load_cells(path: Path, *, columns: int = 4, rows: int = 2) -> list[Image.Image]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
    cell_width = sheet.width // columns
    cell_height = sheet.height // rows
    if sheet.width % columns or sheet.height % rows:
        raise ValueError(f"Sprite sheet is not evenly divisible: {path}")
    return [
        sheet.crop(
            (
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                (row + 1) * cell_height,
            )
        )
        for row in range(rows)
        for column in range(columns)
    ]


def normalize_cells(cells: list[Image.Image], *, target_height: int) -> list[Image.Image]:
    """Crop transparent padding and put every pose on one stable foot canvas."""

    normalized: list[Image.Image] = []
    for cell in cells:
        bbox = cell.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError("Sprite cell has no visible pixels")
        cropped = cell.crop(bbox)
        scale = target_height / max(1, cropped.height)
        target_width = max(1, round(cropped.width * scale))
        fitted = cropped.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
        canvas = Image.new("RGBA", (target_width + 24, target_height), (0, 0, 0, 0))
        canvas.alpha_composite(fitted, ((canvas.width - fitted.width) // 2, 0))
        normalized.append(canvas)
    return normalized


def make_background() -> Image.Image:
    with Image.open(BACKGROUND_PATH) as source:
        background = source.convert("RGB")
    # The crop keeps the castle and the lower path visible while the camera
    # remains completely static throughout the stop.
    return ImageOps.fit(
        background,
        (WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.58, 0.70),
    ).convert("RGBA")


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
        return "last plant"
    return "idle hold"


def sprite_for_time(run_cells: list[Image.Image], second: float) -> Image.Image:
    """Select a readable cadence, then freeze a planted right-facing pose."""

    if second < RUN_END_TIME:
        cycle = int(second * 9.0) % 8
        return run_cells[cycle]
    if second < BRAKE_END_TIME:
        local = (second - RUN_END_TIME) / (BRAKE_END_TIME - RUN_END_TIME)
        # The cadence stretches as velocity falls; every pose still faces right.
        cycle = int((local * 2.8 + 0.1) * 8.0) % 8
        return run_cells[cycle]
    if second < PLANT_END_TIME:
        plant_sequence = (1, 3, 5, 6, 6)
        local = (second - BRAKE_END_TIME) / (PLANT_END_TIME - BRAKE_END_TIME)
        index = min(int(local * len(plant_sequence)), len(plant_sequence) - 1)
        return run_cells[plant_sequence[index]]
    # Frame 6 is a right-facing, weight-settled pose. Holding it avoids a
    # front-facing turn at the moment of stopping and makes the contact stable.
    return run_cells[6]


def position_for_time(second: float) -> tuple[float, float]:
    if second < RUN_END_TIME:
        progress = second / RUN_END_TIME
        return RUN_START_X + (RUN_BRAKE_X - RUN_START_X) * progress, GROUND_Y
    if second < BRAKE_END_TIME:
        progress = (second - RUN_END_TIME) / (BRAKE_END_TIME - RUN_END_TIME)
        return RUN_BRAKE_X + (FINAL_X - RUN_BRAKE_X) * ease_out_cubic(progress), GROUND_Y
    return FINAL_X, GROUND_Y


def composite_frame(
    background: Image.Image,
    sprite: Image.Image,
    *,
    center_x: float,
    ground_y: float,
    second: float,
) -> Image.Image:
    frame = background.copy()
    draw = ImageDraw.Draw(frame, "RGBA")

    # A quiet fixed marker and shadow keep the foot contact point visible even
    # when the character is between run poses.
    draw.ellipse(
        (FINAL_X - 42, ground_y - 5, FINAL_X + 42, ground_y + 8),
        fill=(236, 214, 165, 48),
        outline=(255, 235, 190, 84),
        width=2,
    )
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

    # A tiny deceleration settle keeps the planted boot in the same ground
    # coordinate without introducing camera shake or visible sliding.
    settle = 0.0
    if BRAKE_END_TIME <= second < PLANT_END_TIME:
        settle = 2.0 * (1.0 - ease_in_out((second - BRAKE_END_TIME) / 0.60))
    elif second >= PLANT_END_TIME:
        settle = 0.0
    target_height = 252
    scale = target_height / max(1, sprite.height)
    target_width = max(1, round(sprite.width * scale))
    rendered = sprite.resize((target_width, target_height), Image.Resampling.LANCZOS)
    x = round(center_x - rendered.width / 2)
    y = round(ground_y - target_height - settle)
    frame.alpha_composite(rendered, (x, y))
    return frame.convert("RGB")


def build_frames(*, fps: int, duration: float) -> tuple[list[np.ndarray], list[str]]:
    background = make_background()
    run_cells = normalize_cells(load_cells(RUN_SHEET_PATH), target_height=252)
    # Load the existing stand sheet as an input contract check. The stop keeps
    # the run-facing pose for identity and direction continuity, but the asset
    # remains available for future provider-side stop policy work.
    stand_cells = normalize_cells(load_cells(STAND_SHEET_PATH), target_height=252)
    if len(stand_cells) != 8:
        raise ValueError("Expected the male_01 stand sheet to contain eight cells")

    total_frames = round(duration * fps)
    frames: list[np.ndarray] = []
    phases: list[str] = []
    for index in range(total_frames):
        second = index / fps
        phase = phase_for_time(second)
        frame = composite_frame(
            background,
            sprite_for_time(run_cells, second),
            center_x=position_for_time(second)[0],
            ground_y=position_for_time(second)[1],
            second=second,
        )
        frames.append(np.asarray(frame, dtype=np.uint8))
        phases.append(phase)
    return frames, phases


def write_video(path: Path, frames: list[np.ndarray], *, fps: int) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(path),
        fps=fps,
        codec="libx264",
        quality=8,
        macro_block_size=2,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(frame)
    finally:
        writer.close()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer returned no output: {path}")
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    measured_fps = float(metadata.get("fps") or 0.0)
    report = {
        "path": str(path.resolve()),
        "resolution": list(metadata.get("size") or ()),
        "fps": measured_fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / measured_fps, 3) if measured_fps else 0.0,
        "codec": metadata.get("codec", "h264"),
    }
    if tuple(report["resolution"]) != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution: {report}")
    if frame_count != len(frames) or abs(measured_fps - fps) > 0.01:
        raise RuntimeError(f"Unexpected video metadata: {report}")
    return report


def make_contact_sheet(
    path: Path,
    frames: list[np.ndarray],
    *,
    fps: int,
    columns: int = 4,
    frame_width: int = 320,
) -> None:
    sample_count = 16
    label_height = 34
    frame_height = round(frame_width * HEIGHT / WIDTH)
    rows = (sample_count + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * frame_width, rows * (frame_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    for sample_index in range(sample_count):
        frame_index = min(round(sample_index * (len(frames) - 1) / (sample_count - 1)), len(frames) - 1)
        second = frame_index / fps
        phase = phase_for_time(second)
        frame = Image.fromarray(frames[frame_index]).resize(
            (frame_width, frame_height), Image.Resampling.LANCZOS
        )
        x = (sample_index % columns) * frame_width
        y = (sample_index // columns) * (frame_height + label_height)
        sheet.paste(frame, (x, y + label_height))
        draw.rectangle((x, y, x + frame_width - 1, y + label_height - 1), fill=(244, 246, 249))
        draw.text((x + 8, y + 8), f"{second:0.2f}s  {phase}", fill=(30, 38, 48), font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)


def main() -> None:
    args = parse_args()
    validate_assets()
    fps = min(max(int(args.fps), 6), 30)
    duration = min(max(float(args.duration), 5.0), 15.0)
    frames, phases = build_frames(fps=fps, duration=duration)
    video_report = write_video(args.output, frames, fps=fps)
    make_contact_sheet(args.contact_sheet, frames, fps=fps)
    report = {
        "video": video_report,
        "contact_sheet": str(args.contact_sheet.resolve()),
        "character": "male_01",
        "source_sheets": [str(RUN_SHEET_PATH.resolve()), str(STAND_SHEET_PATH.resolve())],
        "phases": {
            "run": f"0.00-{RUN_END_TIME:.2f}s",
            "brake": f"{RUN_END_TIME:.2f}-{BRAKE_END_TIME:.2f}s",
            "last plant": f"{BRAKE_END_TIME:.2f}-{PLANT_END_TIME:.2f}s",
            "idle hold": f"{PLANT_END_TIME:.2f}-{duration:.2f}s",
        },
        "ground_anchor_y": GROUND_Y,
        "phase_frame_counts": {
            phase: phases.count(phase) for phase in ("run", "brake", "last plant", "idle hold")
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
