"""Render the standalone male_01 run toward the fantasy castle."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import imageio.v2 as imageio


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "DB연결 테스트"
WIDTH = 768
HEIGHT = 384
FPS = 24
DURATION_SECONDS = 4.0
sys.path.insert(0, str(BACKEND))


CHARACTER_KEY = "male_01"
BACKGROUND_KEY = "fantasy_castle"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
CHARACTER_PATH = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
RUN_CYCLE_PATH = (
    ROOT / "assets" / "characters" / "motion_sheets" / "male_01_run_cycle_v16.png"
)
DEFAULT_OUTPUT = ROOT / "output" / "video_previews" / "male_01_run_v1.mp4"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--duration", type=float, default=DURATION_SECONDS)
    parser.add_argument("--fps", type=int, default=FPS)
    return parser.parse_args()


def _validate_inputs() -> None:
    for path in (BACKGROUND_PATH, CHARACTER_PATH, RUN_CYCLE_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required asset was not found: {path}")
    if BACKEND != ROOT / "DB연결 테스트" or not (BACKEND / "hf_video_provider.py").is_file():
        raise RuntimeError(f"Backend path is invalid: {BACKEND}")


def _verify_video(
    path: Path,
    expected_fps: int,
    expected_duration: float,
) -> dict[str, object]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    measured_fps = float(metadata.get("fps") or 0.0)
    duration = frame_count / measured_fps if measured_fps else 0.0
    resolution = tuple(metadata.get("size") or ())
    verification = {
        "path": str(path.resolve()),
        "duration_seconds": round(duration, 3),
        "fps": measured_fps,
        "frame_count": frame_count,
        "resolution": list(resolution),
        "codec": "H.264/libx264",
    }
    if resolution != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution: {verification}")
    if frame_count != round(expected_duration * expected_fps):
        raise RuntimeError(f"Unexpected frame count: {verification}")
    if abs(measured_fps - expected_fps) > 0.01:
        raise RuntimeError(f"Unexpected FPS: {verification}")
    if abs(duration - expected_duration) > (1.0 / expected_fps):
        raise RuntimeError(f"Unexpected duration: {verification}")
    return verification


async def _render(args: argparse.Namespace) -> dict[str, object]:
    _validate_inputs()
    duration = max(1.0, min(float(args.duration), 15.0))
    fps = min(max(int(args.fps), 6), 30)
    frame_count = round(duration * fps)
    # The provider enforces its default duration when normalizing frame counts.
    # Set it for this standalone render before importing the provider module.
    os.environ["LOCAL_VIDEO_DURATION_SECONDS"] = str(duration)
    from hf_video_provider import generate_hf_fairytale_video

    background_bytes = BACKGROUND_PATH.read_bytes()

    generated = await generate_hf_fairytale_video(
        image_bytes=background_bytes,
        story_text=(
            "The young hero runs along the stone path toward the glowing castle. "
            "He keeps his body, face, and gaze aimed toward the castle while his "
            "feet alternate in a clear running cycle."
        ),
        genre="fantasy",
        age="7",
        width=WIDTH,
        height=HEIGHT,
        num_frames=frame_count,
        frame_rate=fps,
        steps=3,
        motion_context={
            "background_key": BACKGROUND_KEY,
            "background_bytes": background_bytes,
            "character_key": CHARACTER_KEY,
            "character_pose": "walking",
            "character_bytes": CHARACTER_PATH.read_bytes(),
            "character_run_cycle_sheet_bytes": RUN_CYCLE_PATH.read_bytes(),
            "action_tags": ["running"],
            "motion_modifier_tags": ["fast_agile"],
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
            },
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(generated["video_bytes"])
    verification = _verify_video(args.output, fps, duration)
    return {
        "verification": verification,
        "animation_mode": generated["parameters"].get("animation_mode"),
        "journey_route": generated["parameters"].get("journey_route"),
    }


def main() -> None:
    result = asyncio.run(_render(_parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
