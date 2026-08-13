"""Render a short, standalone male_01 standing-up action preview."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    _blend_bottom_aligned,
    _fit_background,
    _load_video_dependencies,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
)


FPS = 24
WIDTH = 768
HEIGHT = 384
DURATION = 4.0
OUTPUT = ROOT / "output" / "video_previews" / "male_01_stand_v1.mp4"
SHEET = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_stand_cycle_v1.png"
REFERENCE = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
BACKGROUND = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    return parser.parse_args()


def _validate_inputs() -> None:
    for path in (SHEET, REFERENCE, BACKGROUND):
        if not path.is_file():
            raise FileNotFoundError(f"Missing input asset: {path}")


def _pose(cells, progress: float, Image, interpolate_cache: dict):
    """Traverse the authored stand poses once: crouch, rise, upright, recover."""
    progress = min(max(progress, 0.0), 1.0)
    # Hold the low start and upright finish briefly so the action reads clearly.
    if progress < 0.10:
        return cells[0]
    if progress > 0.91:
        return cells[-1]
    position = ((progress - 0.10) / 0.81) * (len(cells) - 1)
    first = int(position)
    blend = position - first
    if blend < 0.02:
        return cells[first]
    key = (first, round(blend, 3))
    if key not in interpolate_cache:
        interpolate_cache[key] = _blend_bottom_aligned(
            cells[first], cells[min(first + 1, len(cells) - 1)], blend, Image
        )
    return interpolate_cache[key]


def _render(args: argparse.Namespace) -> dict:
    _validate_inputs()
    imageio_dep, np_dep, ImageDep, ImageDrawDep, _, ImageFilter, ImageOps = _load_video_dependencies()
    video_imageio = imageio_dep if imageio_dep is not imageio else imageio
    fps = min(max(int(args.fps), 12), 30)
    width = max(256, int(args.width))
    height = max(128, int(args.height))
    total_frames = round(DURATION * fps)

    sheet = ImageDep.open(SHEET).convert("RGBA")
    reference = ImageDep.open(REFERENCE).convert("RGBA")
    background = ImageDep.open(BACKGROUND).convert("RGBA")
    cells = _prepare_motion_sheet(sheet, ImageDep)
    if len(cells) != 8:
        raise ValueError(f"Expected 8 authored stand poses, got {len(cells)}")
    alpha = sheet.getchannel("A")
    if alpha.getbbox() is None or alpha.getextrema() == (255, 255):
        raise ValueError("The stand motion sheet must retain transparent background")

    cache = {}

    def frames():
        plan = {
            "action": "stand",
            "target": "castle",
            "background_key": "fantasy_castle",
            "motion_focus": "character",
            "pace": "stationary",
            "_duration_seconds": DURATION,
        }
        for index in range(total_frames):
            progress = index / max(total_frames - 1, 1)
            frame = _fit_background(
                background,
                ImageDep,
                ImageOps,
                width,
                height,
                progress,
                plan,
            )
            pose = _pose(cells, progress, ImageDep, cache)
            # Keep the character grounded while the castle remains a stable scene.
            _paste_character_layer(
                frame=frame,
                character_image=pose,
                Image=ImageDep,
                ImageDraw=ImageDrawDep,
                ImageFilter=ImageFilter,
                center_x=width * 0.42,
                ground_y=height * 0.91,
                scale=0.66,
                rotation=0.0,
                ground_contact=1.0,
            )
            yield frame.convert("RGB")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    video_bytes = _write_video_frames(
        output_path=args.output,
        frame_rate=fps,
        frames=frames(),
        imageio=video_imageio,
        np=np_dep,
    )
    metadata = {
        "output": str(args.output),
        "character_reference": str(REFERENCE),
        "background": str(BACKGROUND),
        "motion_sheet": str(SHEET),
        "duration_seconds": DURATION,
        "fps": fps,
        "frame_count": total_frames,
        "resolution": [width, height],
        "codec": "H.264 via imageio/ffmpeg",
        "motion_phases": ["low posture", "extend body", "balance recovery"],
        "bytes": len(video_bytes),
    }
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return metadata


def main() -> None:
    _render(_args())


if __name__ == "__main__":
    main()
