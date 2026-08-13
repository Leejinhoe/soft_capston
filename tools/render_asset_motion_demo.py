"""Render a story motion demo from the selected character's custom action sheets.

This is a preview assembler, not a replacement for the FastAPI video contract. It
reuses the provider's background fitting, character compositing, sprite-sheet
preparation, and MP4 encoding helpers while allowing one scene to contain several
custom action sheets.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    BACKGROUND_JOURNEY_ROUTES,
    _blend_bottom_aligned,
    _fit_background,
    _load_video_dependencies,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
    _character_motion_values,
)


FPS = 24
WIDTH = 768
HEIGHT = 384
EXPECTED_CELLS = 8
OUTPUT_V1 = ROOT / "output" / "video_previews" / "male_01_asset_motion_demo_v1.mp4"
CONTACT_V1 = ROOT / "output" / "video_previews" / "male_01_asset_motion_demo_v1_contact.png"
OUTPUT_V2 = ROOT / "output" / "video_previews" / "male_01_asset_motion_demo_v2.mp4"
CONTACT_V2 = ROOT / "output" / "video_previews" / "male_01_asset_motion_demo_v2_contact.png"


@dataclass(frozen=True)
class Segment:
    name: str
    start: float
    end: float
    sheet_name: str
    background_action: str
    placement: str

    @property
    def duration(self) -> float:
        return self.end - self.start


SEGMENTS = (
    Segment("SIT", 0.0, 2.5, "sit", "sit", "ground"),
    Segment("STAND", 2.5, 4.5, "stand", "stand", "ground"),
    Segment("CRAWL TO CASTLE", 4.5, 7.5, "crawl", "journey", "route"),
    Segment("CLIMB ROCK WALL", 7.5, 10.5, "climb", "journey", "climb"),
    Segment("ARRIVE", 10.5, 12.5, "stand", "stand", "ground"),
)


SHEET_PATHS = {
    "sit": ROOT / "assets" / "characters" / "motion_sheets" / "male_01_sit_cycle_v1.png",
    "stand": ROOT / "assets" / "characters" / "motion_sheets" / "male_01_stand_cycle_v1.png",
    "crawl": ROOT / "assets" / "characters" / "motion_sheets" / "male_01_crawl_cycle_v1.png",
    "climb": ROOT / "assets" / "characters" / "motion_sheets" / "male_01_climb_cycle_v1.png",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--contact", type=Path, default=None)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    return parser.parse_args()


def _load_and_validate_sheets(Image):
    loaded = {}
    validation = {}
    for name, path in SHEET_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing motion sheet: {path}")
        image = Image.open(path).convert("RGBA")
        alpha = image.getchannel("A")
        if alpha.getbbox() is None or alpha.getextrema() == (255, 255):
            raise ValueError(f"Motion sheet must contain transparent pixels: {path}")
        cells = _prepare_motion_sheet(image, Image)
        if len(cells) != EXPECTED_CELLS:
            raise ValueError(f"Expected {EXPECTED_CELLS} cells in {path}, got {len(cells)}")
        loaded[name] = cells
        validation[name] = {
            "path": str(path),
            "size": list(image.size),
            "mode": image.mode,
            "cells": len(cells),
            "alpha_extrema": list(alpha.getextrema()),
        }
    return loaded, validation


def _segment_at(seconds: float) -> tuple[Segment, float]:
    for segment in SEGMENTS:
        if seconds < segment.end:
            local = (seconds - segment.start) / segment.duration
            return segment, min(max(local, 0.0), 1.0)
    last = SEGMENTS[-1]
    return last, 1.0


def _select_custom_pose(
    cells,
    local: float,
    *,
    cycle: bool,
    Image,
    cv2,
    np,
    cache,
    sequence=None,
    hold_last: bool = True,
    interpolate: bool = True,
):
    """Use the eight authored poses with short holds at each action boundary."""
    sequence = tuple(sequence or range(len(cells)))
    if local <= 0.12:
        return cells[sequence[0]]
    if hold_last and local >= 0.92:
        return cells[sequence[-1]]
    active = (local - 0.12) / 0.80
    if cycle:
        position = (active * 1.65 * (len(sequence) - 1)) % len(sequence)
    else:
        position = active * (len(sequence) - 1)
    first = sequence[int(position) % len(sequence)]
    second = sequence[(int(position) + 1) % len(sequence)]
    blend = position - int(position)
    if not interpolate:
        return cells[first if blend < 0.5 else second]
    if blend < 0.02:
        return cells[first]
    return _blend_bottom_aligned(cells[first], cells[second], blend, Image)


def _route_plan(progress: float) -> dict:
    return {
        "action": "journey",
        "target": "castle",
        "background_key": "fantasy_castle",
        "pace": "walk",
        "motion_focus": "character",
        "path_pattern": "direct",
        "_duration_seconds": 3.0,
    }


def _stationary_plan(action: str) -> dict:
    return {
        "action": action,
        "target": "castle",
        "background_key": "fantasy_castle",
        "pace": "walk",
        "motion_focus": "character",
        "_duration_seconds": 2.5,
    }


def _draw_climb_reference(frame, Image, ImageDraw, local: float):
    """Add an irregular stone face so the climbing action has a visible anchor."""
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    left = int(frame.width * 0.51)
    right = int(frame.width * 0.90)
    top = int(frame.height * (0.18 - local * 0.06))
    bottom = frame.height
    wall = [
        (left + 18, bottom),
        (left - 8, top + 78),
        (left + 20, top + 30),
        (left + 70, top + 42),
        (left + 112, top),
        (right - 34, top + 22),
        (right + 8, top + 90),
        (right - 12, bottom),
    ]
    draw.polygon(wall, fill=(54, 69, 104, 105), outline=(179, 193, 225, 135))
    for row in range(4):
        y = top + 42 + row * 55
        offset = 24 if row % 2 else 0
        for column in range(3):
            x = left + 24 + column * 94 + offset
            draw.line((x, y, x - 18, y + 28), fill=(196, 203, 225, 95), width=2)
    frame.alpha_composite(overlay)


def _draw_climb_reference_v2(frame, ImageDraw):
    """Place one opaque, quiet stone wall on the right side of the frame."""
    width, height = frame.size
    left = int(width * 0.62)
    right = int(width * 0.94)
    top = int(height * 0.08)
    wall = [
        (left + 14, height),
        (left, top + 34),
        (left + 28, top),
        (right - 20, top + 10),
        (right, top + 52),
        (right - 8, height),
    ]
    draw = ImageDraw.Draw(frame)
    draw.polygon(wall, fill=(84, 92, 108, 255))
    draw.line(wall + [wall[0]], fill=(43, 50, 65, 255), width=4, joint="curve")
    for row in range(5):
        y = top + 52 + row * 54
        draw.line((left + 10, y, right - 12, y + 5), fill=(143, 151, 165, 255), width=2)
        for column in range(2):
            x = left + 58 + column * 82 + (18 if row % 2 else 0)
            draw.line((x, y - 50, x - 8, y), fill=(55, 63, 78, 255), width=2)


def _render(args: argparse.Namespace) -> tuple[Path, Path, dict]:
    imageio_dep, np_dep, ImageDep, ImageDrawDep, ImageEnhance, ImageFilter, ImageOps = _load_video_dependencies()
    if imageio_dep is not imageio:
        # Keep the provider's dependency contract authoritative in environments
        # where imageio is supplied through a different import alias.
        imageio_local = imageio_dep
    else:
        imageio_local = imageio

    character_path = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
    background_path = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
    character = ImageDep.open(character_path).convert("RGBA")
    background = ImageDep.open(background_path).convert("RGBA")
    sheets, validation = _load_and_validate_sheets(ImageDep)
    cv2 = None
    try:
        import cv2 as cv2_module

        cv2 = cv2_module
    except ImportError:
        pass

    fps = min(max(int(args.fps), 12), 30)
    width = max(256, int(args.width))
    height = max(128, int(args.height))
    duration = SEGMENTS[-1].end
    total_frames = round(duration * fps)
    interpolation_cache = {}
    use_v2_climb = args.version == "v2"

    def frames():
        for index in range(total_frames):
            seconds = index / fps
            segment, local = _segment_at(seconds)
            if segment.placement == "route":
                plan = _route_plan(local)
            elif segment.placement == "climb":
                plan = _route_plan(local)
            else:
                plan = _stationary_plan(segment.background_action)

            frame = _fit_background(
                background,
                ImageDep,
                ImageOps,
                width,
                height,
                local,
                plan,
            )
            if segment.placement == "route":
                values = _character_motion_values(
                    action="journey",
                    progress=local,
                    width=width,
                    height=height,
                    motion_strength=2,
                    motion_plan=plan,
                )
                pose = _select_custom_pose(
                    sheets[segment.sheet_name],
                    local,
                    cycle=True,
                    Image=ImageDep,
                    cv2=cv2,
                    np=np_dep,
                    cache=interpolation_cache,
                )
            elif segment.placement == "climb":
                if use_v2_climb:
                    _draw_climb_reference_v2(frame, ImageDrawDep)
                else:
                    _draw_climb_reference(frame, ImageDep, ImageDrawDep, local)
                pose = _select_custom_pose(
                    sheets[segment.sheet_name],
                    local,
                    cycle=True,
                    Image=ImageDep,
                    cv2=cv2,
                    np=np_dep,
                    cache=interpolation_cache,
                    sequence=(0, 1, 2, 3, 4, 5, 6, 7) if use_v2_climb else (0, 1, 2, 3, 4, 5),
                    hold_last=False,
                    interpolate=not use_v2_climb,
                )
                # The camera continues toward the castle, while the hero climbs
                # the visible stone face instead of sliding along the road.
                values = {
                    "center_x": width * (0.59 - 0.02 * local),
                    "ground_y": height * (0.92 - 0.30 * local),
                    "scale": 0.62 if use_v2_climb else 0.64,
                    "rotation": 0.0,
                    "ground_contact": 0.25,
                }
            else:
                values = _character_motion_values(
                    action=segment.background_action,
                    progress=local,
                    width=width,
                    height=height,
                    motion_strength=2,
                    motion_plan=plan,
                )
                pose = _select_custom_pose(
                    sheets[segment.sheet_name],
                    local,
                    cycle=False,
                    Image=ImageDep,
                    cv2=cv2,
                    np=np_dep,
                    cache=interpolation_cache,
                )
            _paste_character_layer(
                frame=frame,
                character_image=pose,
                Image=ImageDep,
                ImageDraw=ImageDrawDep,
                ImageFilter=ImageFilter,
                center_x=values["center_x"],
                ground_y=values["ground_y"],
                scale=values["scale"],
                rotation=values["rotation"],
                ground_contact=values.get("ground_contact", 1.0),
            )
            frame = ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015)
            yield frame

    args.output.parent.mkdir(parents=True, exist_ok=True)
    video_bytes = _write_video_frames(
        output_path=args.output,
        frame_rate=fps,
        frames=frames(),
        imageio=imageio_local,
        np=np_dep,
    )
    _write_contact_sheet(args.output, args.contact, fps, ImageDep, ImageDrawDep, imageio_local)
    metadata = {
        "character": str(character_path),
        "background": str(background_path),
        "duration_seconds": duration,
        "fps": fps,
        "frame_count": total_frames,
        "resolution": [width, height],
        "segments": [segment.__dict__ | {"duration": segment.duration} for segment in SEGMENTS],
        "sheets": validation,
        "provider_helpers_reused": [
            "_prepare_motion_sheet",
            "_fit_background",
            "_character_motion_values",
            "_paste_character_layer",
            "_write_video_frames",
        ],
        "bytes": len(video_bytes),
        "version": args.version,
    }
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return args.output, args.contact, metadata


def _write_contact_sheet(video: Path, output: Path, fps: int, Image, ImageDraw, imageio):
    reader = imageio.get_reader(str(video))
    try:
        count = reader.count_frames()
        samples = 13
        source = Image.fromarray(reader.get_data(0)).convert("RGB")
        thumb_w = 256
        thumb_h = round(thumb_w * source.height / source.width)
        label_h = 28
        cols = 4
        rows = (samples + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for i in range(samples):
            frame_index = round(i * (count - 1) / (samples - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = (i % cols) * thumb_w
            y = (i // cols) * (thumb_h + label_h)
            sheet.paste(frame, (x, y + label_h))
            seconds = frame_index / fps
            segment, _ = _segment_at(seconds)
            draw.text((x + 8, y + 7), f"{seconds:04.1f}s  {segment.name}", fill="black")
    finally:
        reader.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> None:
    args = _parse_args()
    if args.output is None:
        args.output = OUTPUT_V2 if args.version == "v2" else OUTPUT_V1
    if args.contact is None:
        args.contact = CONTACT_V2 if args.version == "v2" else CONTACT_V1
    _render(args)


if __name__ == "__main__":
    main()
