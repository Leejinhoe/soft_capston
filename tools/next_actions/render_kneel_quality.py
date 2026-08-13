"""Render a diagnostic kneel preview from the existing male_01 sit sheet.

This intentionally uses only the authored sit-cycle cells that show a knee
contact.  Deep seated cells are excluded so the result can be judged against
the existing sit preview before a dedicated kneel sheet is commissioned.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
BACKEND = next(
    path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file()
)
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    _fit_background,
    _load_video_dependencies,
    _optical_flow_interpolate,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
)


CHARACTER = "male_01"
FPS = 30
WIDTH = 960
HEIGHT = 480
DURATION = 6.0
EXPECTED_CELLS = 8

SIT_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / f"{CHARACTER}_sit_cycle_v1.png"
BACKGROUND = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
OUTPUT_DIR = ROOT / "output" / "video_previews"
OUTPUT = OUTPUT_DIR / f"{CHARACTER}_kneel_quality_v1.mp4"
CONTACT = OUTPUT_DIR / f"{CHARACTER}_kneel_quality_v1_contact.png"
REPORT = OUTPUT_DIR / f"{CHARACTER}_kneel_quality_v1_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--contact", type=Path, default=CONTACT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION)
    return parser.parse_args()


def _smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def _load_cells(Image):
    if not SIT_SHEET.is_file():
        raise FileNotFoundError(SIT_SHEET)
    if not BACKGROUND.is_file():
        raise FileNotFoundError(BACKGROUND)
    with Image.open(SIT_SHEET) as source:
        sheet = source.convert("RGBA")
    cells = _prepare_motion_sheet(sheet, Image)
    if len(cells) != EXPECTED_CELLS:
        raise ValueError(f"Expected {EXPECTED_CELLS} sit cells, got {len(cells)}")
    with Image.open(BACKGROUND) as source:
        background = source.convert("RGBA")
    return cells, background


def _keyframes():
    """Stand -> lower -> one-knee contact -> hold -> stand recovery."""

    return (
        (0.00, 0),
        (0.10, 0),
        (0.24, 1),
        (0.38, 2),
        (0.52, 2),
        (0.64, 6),
        (0.80, 6),
        (0.92, 7),
        (1.00, 7),
    )


def _phase_for_progress(progress: float) -> str:
    if progress < 0.24:
        return "lowering"
    if progress < 0.64:
        return "knee contact"
    if progress < 0.80:
        return "kneel hold"
    return "recovery"


def _pose_at(keyframes, progress: float, cells, Image, cv2, np, cache: dict):
    value = min(max(float(progress), 0.0), 1.0)
    if value <= keyframes[0][0]:
        return cells[keyframes[0][1]]
    for (start, first), (end, second) in zip(keyframes, keyframes[1:]):
        if value > end:
            continue
        if first == second or end <= start:
            return cells[first]
        local = _smoothstep((value - start) / (end - start))
        cache_key = ("kneel-flow", first, second)
        return _optical_flow_interpolate(
            cells[first],
            cells[second],
            local,
            Image=Image,
            cv2=cv2,
            np=np,
            cache=cache,
            cache_key=cache_key,
        )
    return cells[keyframes[-1][1]]


def render_frames(*, fps: int, duration: float, dependencies, cv2, cells, background):
    imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps = dependencies
    total_frames = max(2, round(duration * fps))
    cache = {}
    keyframes = _keyframes()
    plan = {
        "action": "idle",
        "target": "scene",
        "background_key": "fantasy_castle",
        "motion_focus": "character",
        "camera_motion": "locked",
    }
    locked_background = _fit_background(
        background, Image, ImageOps, WIDTH, HEIGHT, 0.0, plan
    )
    frames = []
    phases = []
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
            center_x=WIDTH * 0.46,
            ground_y=HEIGHT * 0.92,
            scale=0.66,
            rotation=0.0,
            ground_contact=1.0,
        )
        frames.append(ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015))
        phases.append(_phase_for_progress(progress))
    return frames, phases


def write_contact_sheet(path: Path, frames, phases, *, fps: int, Image, ImageDraw):
    sample_count = 12
    columns = 4
    tile_width = 240
    label_height = 30
    tile_height = round(tile_width * HEIGHT / WIDTH)
    rows = (sample_count + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * tile_width, rows * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    for sample_index in range(sample_count):
        frame_index = min(
            round(sample_index * (len(frames) - 1) / (sample_count - 1)),
            len(frames) - 1,
        )
        second = frame_index / fps
        tile = frames[frame_index].resize(
            (tile_width, tile_height), Image.Resampling.LANCZOS
        )
        x = (sample_index % columns) * tile_width
        y = (sample_index // columns) * (tile_height + label_height)
        sheet.paste(tile, (x, y + label_height))
        draw.rectangle(
            (x, y, x + tile_width - 1, y + label_height - 1),
            fill=(244, 246, 249),
        )
        draw.text(
            (x + 7, y + 7),
            f"{second:0.2f}s  {phases[frame_index]}",
            fill=(30, 38, 48),
            font=font,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)


def main() -> None:
    args = parse_args()
    fps = min(max(int(args.fps), 12), 30)
    duration = min(max(float(args.duration), 4.0), 15.0)
    dependencies = _load_video_dependencies()
    imageio, np, Image, ImageDraw, _, _, _ = dependencies
    try:
        import cv2
    except ImportError:
        cv2 = None
    cells, background = _load_cells(Image)
    frames, phases = render_frames(
        fps=fps,
        duration=duration,
        dependencies=dependencies,
        cv2=cv2,
        cells=cells,
        background=background,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    video_bytes = _write_video_frames(
        output_path=args.output,
        frame_rate=fps,
        frames=frames,
        imageio=imageio,
        np=np,
    )
    write_contact_sheet(args.contact, frames, phases, fps=fps, Image=Image, ImageDraw=ImageDraw)
    reader = imageio.get_reader(str(args.output))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    measured_fps = float(metadata.get("fps") or 0.0)
    report = {
        "status": "diagnostic_preview",
        "action": "kneel",
        "character": CHARACTER,
        "diagnostic_verdict": "needs_dedicated_kneel_asset",
        "observations": [
            "one knee contact is visible in the selected source cells",
            "the current kneel hold keeps the torso forward and crouched",
            "the source does not provide a sufficiently upright kneel hold distinct from sit",
            "this preview is not registered as a production provider action",
        ],
        "video": {
            "path": str(args.output.resolve()),
            "resolution": list(metadata.get("size") or ()),
            "fps": measured_fps,
            "frame_count": frame_count,
            "duration_seconds": round(frame_count / measured_fps, 3) if measured_fps else 0.0,
            "codec": metadata.get("codec", "h264"),
            "bytes": len(video_bytes),
        },
        "contact_sheet": str(args.contact.resolve()),
        "source_asset": str(SIT_SHEET.resolve()),
        "cell_contract": {
            "standing": 0,
            "lowering": 1,
            "knee_contact": 2,
            "kneel_hold": 6,
            "recovery": 7,
            "excluded_seated_cells": [3, 4, 5],
        },
        "quality_gates": [
            "one knee visibly contacts the ground",
            "torso remains upright during kneel hold",
            "feet/root stay ground aligned",
            "deep seated cells are not used",
            "male_01 identity remains consistent",
        ],
        "phase_frame_counts": {
            phase: phases.count(phase)
            for phase in ("lowering", "knee contact", "kneel hold", "recovery")
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
