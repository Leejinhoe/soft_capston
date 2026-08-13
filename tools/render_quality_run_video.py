"""Render a quality-checked character run toward the fantasy castle."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import imageio.v2 as imageio


ROOT = Path(__file__).resolve().parents[1]
BACKEND = next(
    path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file()
)
ASSET_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output" / "video_previews"
DEFAULT_CHARACTER_KEY = "male_01"
BACKGROUND_KEY = "fantasy_castle"
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 480
DEFAULT_FPS = 30
DEFAULT_DURATION = 8.0

sys.path.insert(0, str(BACKEND))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character-key", default=DEFAULT_CHARACTER_KEY)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    return parser.parse_args()


def verify_video(path: Path, *, width: int, height: int, fps: int, duration: float):
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()

    measured_fps = float(metadata.get("fps") or 0.0)
    measured_duration = frame_count / measured_fps if measured_fps else 0.0
    measured_size = tuple(metadata.get("size") or ())
    expected_frames = round(duration * fps)
    report = {
        "path": str(path.resolve()),
        "resolution": list(measured_size),
        "fps": measured_fps,
        "frame_count": frame_count,
        "duration_seconds": round(measured_duration, 3),
        "codec": metadata.get("codec", "h264"),
    }
    if measured_size != (width, height):
        raise RuntimeError(f"Unexpected resolution: {report}")
    if frame_count != expected_frames:
        raise RuntimeError(f"Unexpected frame count: {report}")
    if abs(measured_fps - fps) > 0.01:
        raise RuntimeError(f"Unexpected FPS: {report}")
    if abs(measured_duration - duration) > (1.0 / fps):
        raise RuntimeError(f"Unexpected duration: {report}")
    return report


async def render(args: argparse.Namespace) -> dict:
    duration = min(max(float(args.duration), 1.0), 15.0)
    fps = min(max(int(args.fps), 6), 30)
    width = max(64, int(args.width))
    height = max(64, int(args.height))
    frame_count = round(duration * fps)
    character_key = args.character_key.strip().lower()
    if not (
        character_key.startswith(("male_", "female_"))
        and character_key[-2:].isdigit()
        and 1 <= int(character_key[-2:]) <= 8
    ):
        raise ValueError("--character-key must be male_01..08 or female_01..08")
    output = args.output or (
        OUTPUT_DIR / f"{character_key}_castle_run_quality_v2.mp4"
    )

    background = ASSET_DIR / "backgrounds" / "fantasy_castle_wide_v2.png"
    character = ASSET_DIR / "characters" / f"{character_key}_reference_v2.png"
    run_cycle = (
        ASSET_DIR
        / "characters"
        / "motion_sheets"
        / f"{character_key}_run_cycle_v16.png"
    )
    for asset in (background, character, run_cycle):
        if not asset.is_file():
            raise FileNotFoundError(f"Required asset was not found: {asset}")

    # Supersampling improves sprite edges and shadow stability before the final resize.
    os.environ["LOCAL_VIDEO_RENDER_SCALE"] = "3"
    os.environ["LOCAL_VIDEO_DURATION_SECONDS"] = str(duration)
    os.environ["LOCAL_VIDEO_MAX_DURATION_SECONDS"] = "15"
    os.environ["LOCAL_VIDEO_JOURNEY_PAN_START"] = "0.52"
    os.environ["LOCAL_VIDEO_JOURNEY_PAN_END"] = "0.90"
    os.environ["LOCAL_VIDEO_RUN_SCALE_START"] = "0.42"
    os.environ["LOCAL_VIDEO_RUN_SCALE_END"] = "0.34"
    os.environ["LOCAL_VIDEO_RUN_CYCLES_PER_SECOND"] = "1.0"
    os.environ["LOCAL_VIDEO_RUN_BOB_SCALE"] = "0.004"
    os.environ["LOCAL_VIDEO_RUN_CONTACT_MIN"] = "0.30"

    from hf_video_provider import generate_hf_fairytale_video

    background_bytes = background.read_bytes()
    generated = await generate_hf_fairytale_video(
        image_bytes=background_bytes,
        story_text=(
            "The selected young hero runs continuously along the visible stone path "
            "toward the glowing castle. The body and gaze stay aimed toward the castle, "
            "the feet alternate in a readable grounded running cycle, and the "
            "camera follows the path without sudden jumps."
        ),
        genre="fantasy",
        age="7",
        width=width,
        height=height,
        num_frames=frame_count,
        frame_rate=fps,
        steps=8,
        motion_context={
            "background_key": BACKGROUND_KEY,
            "background_bytes": background_bytes,
            "character_key": character_key,
            "character_pose": "walking",
            "character_bytes": character.read_bytes(),
            "character_run_cycle_sheet_bytes": run_cycle.read_bytes(),
            "action_tags": ["running"],
            "motion_modifier_tags": ["fast_agile", "continuous"],
            "motion_focus": "character",
            "action_semantics": {
                "motion_mode": "locomotion",
                "animation_action": "journey",
                "pace": "run",
                "directionality": "toward_target",
                "path_pattern": "direct",
                "requires_target": True,
                "target_type": "castle",
                "participant_count": 1,
                "body_focus": "alternating_foot_contact",
            },
        },
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(generated["video_bytes"])
    verification = verify_video(
        output,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
    )
    return {
        "character_key": character_key,
        "verification": verification,
        "animation_mode": generated["parameters"].get("animation_mode"),
        "render_scale": generated["parameters"].get("render_scale"),
        "journey_route": generated["parameters"].get("journey_route"),
    }


def main() -> None:
    result = asyncio.run(render(parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
