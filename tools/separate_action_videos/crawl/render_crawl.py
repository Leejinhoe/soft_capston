"""Render the standalone male_01 crawl-to-castle preview.

This renderer intentionally owns one action only. It uses the authored 4x2
crawl sheet, keeps one fixed ground-contact path, and reuses the backend's
background fitting and H.264 helpers without changing backend source files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
BACKEND = next(
    (path for path in ROOT.iterdir() if path.is_dir() and path.name.startswith("DB")),
    None,
)
if BACKEND is None:
    raise RuntimeError("Could not locate the DB backend directory.")
sys.path.insert(0, str(BACKEND))

from hf_video_provider import (  # noqa: E402
    _blend_bottom_aligned,
    _fit_background,
    _load_video_dependencies,
    _paste_character_layer,
    _prepare_motion_sheet,
    _write_video_frames,
)


WIDTH = 768
HEIGHT = 384
FPS = 24
DURATION_SECONDS = 4.0
FRAME_COUNT = round(DURATION_SECONDS * FPS)
EXPECTED_CELLS = 8

SHEET_PATH = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_crawl_cycle_v1.png"
IDENTITY_PATH = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
DEFAULT_OUTPUT = ROOT / "output" / "video_previews" / "male_01_crawl_v1.mp4"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION_SECONDS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    return parser.parse_args()


def _load_sheet(ImageDep):
    if not SHEET_PATH.is_file():
        raise FileNotFoundError(f"Missing crawl sheet: {SHEET_PATH}")
    sheet = ImageDep.open(SHEET_PATH).convert("RGBA")
    cells = _prepare_motion_sheet(sheet, ImageDep)
    if len(cells) != EXPECTED_CELLS:
        raise ValueError(f"Expected {EXPECTED_CELLS} crawl poses, got {len(cells)}")
    if any(cell.getchannel("A").getbbox() is None for cell in cells):
        raise ValueError("Every crawl pose must contain visible pixels")
    return sheet, cells


def _crawl_pose(cells, progress: float, ImageDep):
    """Interpolate one continuous loop across all eight authored poses."""

    normalized = min(max(float(progress), 0.0), 1.0)
    # Briefly establish the first pose, then make 1.35 smooth cycles. The
    # final pose blends back into pose zero instead of cutting at the loop.
    active = min(max((normalized - 0.06) / 0.88, 0.0), 1.0)
    position = (active * 1.35 * len(cells)) % len(cells)
    first_index = int(position) % len(cells)
    second_index = (first_index + 1) % len(cells)
    amount = position - int(position)
    if normalized < 0.06:
        return cells[0]
    return _blend_bottom_aligned(cells[first_index], cells[second_index], amount, ImageDep)


def _motion_plan() -> dict:
    return {
        "action": "journey",
        "target": "castle",
        "background_key": "fantasy_castle",
        "pace": "crawl",
        "motion_focus": "character",
        "path_pattern": "direct",
        "_duration_seconds": DURATION_SECONDS,
    }


def _path_values(progress: float, width: int, height: int) -> dict[str, float]:
    """Move left-to-right while gently climbing the castle road perspective."""

    # Smoothstep avoids a robotic constant-speed start and stop. The fixed
    # ground_y path is shared by every pose, so hands and knees stay grounded.
    eased = progress * progress * (3.0 - 2.0 * progress)
    return {
        "center_x": width * (0.12 + 0.72 * eased),
        "ground_y": height * (0.91 - 0.18 * eased),
        "scale": 0.66 - 0.12 * eased,
        "rotation": 0.0,
        "ground_contact": 0.92,
    }


def _render(args: argparse.Namespace) -> dict:
    imageio_dep, np_dep, ImageDep, ImageDrawDep, ImageEnhance, ImageFilter, ImageOps = (
        _load_video_dependencies()
    )
    fps = min(max(int(args.fps), 12), 30)
    duration = max(1.0, float(args.duration))
    width = max(256, int(args.width))
    height = max(128, int(args.height))
    frame_count = round(duration * fps)

    background = ImageDep.open(BACKGROUND_PATH).convert("RGBA")
    identity = ImageDep.open(IDENTITY_PATH).convert("RGBA")
    if identity.getchannel("A").getbbox() is None:
        raise ValueError("male_01 identity reference is empty")
    sheet, cells = _load_sheet(ImageDep)
    plan = _motion_plan()
    interpolation_cache = {}

    def frames():
        for index in range(frame_count):
            progress = index / max(frame_count - 1, 1)
            frame = _fit_background(
                background,
                ImageDep,
                ImageOps,
                width,
                height,
                progress,
                plan,
            )
            pose = _crawl_pose(cells, progress, ImageDep)
            values = _path_values(progress, width, height)
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
                ground_contact=values["ground_contact"],
            )
            yield ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_video_frames(
        output_path=args.output,
        frame_rate=fps,
        frames=frames(),
        imageio=imageio_dep,
        np=np_dep,
    )

    metadata = {
        "output": str(args.output.resolve()),
        "character": "male_01",
        "identity_reference": str(IDENTITY_PATH),
        "background": str(BACKGROUND_PATH),
        "motion_sheet": str(SHEET_PATH),
        "action": "crawl",
        "direction": "screen_left_to_right_toward_castle",
        "duration_seconds": frame_count / fps,
        "fps": fps,
        "frame_count": frame_count,
        "resolution": [width, height],
        "codec": "libx264",
        "poses": len(cells),
        "interpolated": True,
        "single_character": True,
        "backend": str(BACKEND),
        "motion_sheet_size": list(sheet.size),
    }
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return metadata


def main() -> None:
    _render(_parse_args())


if __name__ == "__main__":
    main()
