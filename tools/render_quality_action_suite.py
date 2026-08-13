"""Render readable non-running solo actions for the selected male_01 character."""

from __future__ import annotations

import asyncio
import argparse
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
CHARACTER_KEY = "male_01"
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION = 6.0

sys.path.insert(0, str(BACKEND))


CASES = (
    {
        "name": "male_01_walk_quality_v2",
        "story": "The young hero walks calmly along the stone path toward the glowing castle.",
        "genre": "fantasy",
        "background": "fantasy_castle_wide_v2.png",
        "background_key": "fantasy_castle",
        "character_pose": "walking",
        "action_tags": ["walking"],
        "motion_sheet": "male_01_motion_sheet_v3.png",
        "motion_field": "character_motion_sheet_bytes",
        "semantics": {
            "motion_mode": "locomotion",
            "animation_action": "journey",
            "pace": "walk",
            "directionality": "toward_target",
            "path_pattern": "direct",
            "requires_target": True,
            "target_type": "castle",
            "participant_count": 1,
        },
    },
    {
        "name": "male_01_jump_quality_v1",
        "story": "The young hero jumps clearly into the air and lands on the path.",
        "genre": "fantasy",
        "background": "fantasy_castle_wide_v2.png",
        "background_key": "fantasy_castle",
        "character_pose": "walking",
        "action_tags": ["jumping"],
        "motion_sheet": "male_01_jump_cycle_v19.png",
        "motion_field": "character_jump_cycle_sheet_bytes",
        "semantics": {
            "motion_mode": "solo",
            "animation_action": "jump",
            "participant_count": 1,
            "requires_partner": False,
            "requires_object": False,
        },
    },
    {
        "name": "male_01_investigate_quality_v1",
        "story": "The young hero stops, looks around, and carefully searches the library for a clue.",
        "genre": "mystery",
        "background": "mystery_library_wide_v2.png",
        "background_key": "mystery_library",
        "character_pose": "walking",
        "action_tags": ["investigating"],
        "motion_sheet": "male_01_action_sheet_v21.png",
        "motion_field": "character_action_sheet_bytes",
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "investigate",
            "participant_count": 1,
            "requires_partner": False,
            "requires_object": False,
        },
    },
    {
        "name": "male_01_magic_quality_v1",
        "story": "The young hero raises his hands and casts a glowing spell in the crystal cave.",
        "genre": "fantasy",
        "background": "fantasy_crystal_cave_wide_v1.png",
        "background_key": "fantasy_crystal_cave",
        "character_pose": "casting-magic",
        "action_tags": ["casting_magic"],
        "effect_tags": ["glowing_light"],
        "motion_sheet": "male_01_magic_cycle_v22.png",
        "motion_field": "character_magic_cycle_sheet_bytes",
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "magic",
            "participant_count": 1,
            "requires_partner": False,
            "requires_object": False,
        },
    },
)


def verify(path: Path) -> dict:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frames = int(reader.count_frames())
    finally:
        reader.close()
    fps = float(metadata.get("fps") or 0.0)
    duration = frames / fps if fps else 0.0
    report = {
        "path": str(path.resolve()),
        "resolution": list(metadata.get("size") or ()),
        "fps": fps,
        "frame_count": frames,
        "duration_seconds": round(duration, 3),
        "codec": metadata.get("codec", "h264"),
    }
    if tuple(report["resolution"]) != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution: {report}")
    if frames != round(DURATION * FPS):
        raise RuntimeError(f"Unexpected frame count: {report}")
    if abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected FPS: {report}")
    return report


async def render_case(case: dict, generate) -> dict:
    background = ASSET_DIR / "backgrounds" / case["background"]
    character = ASSET_DIR / "characters" / f"{CHARACTER_KEY}_reference_v2.png"
    motion_sheet = ASSET_DIR / "characters" / "motion_sheets" / case["motion_sheet"]
    for asset in (background, character, motion_sheet):
        if not asset.is_file():
            raise FileNotFoundError(f"Required asset was not found: {asset}")

    background_bytes = background.read_bytes()
    motion_context = {
        "background_key": case["background_key"],
        "background_bytes": background_bytes,
        "character_key": CHARACTER_KEY,
        "character_pose": case["character_pose"],
        "character_bytes": character.read_bytes(),
        case["motion_field"]: motion_sheet.read_bytes(),
        "action_tags": case.get("action_tags", []),
        "effect_tags": case.get("effect_tags", []),
        "motion_modifier_tags": ["clear_readable", "continuous"],
        "motion_focus": "character",
        "action_semantics": case["semantics"],
    }
    generated = await generate(
        image_bytes=background_bytes,
        story_text=case["story"],
        genre=case["genre"],
        age="7",
        width=WIDTH,
        height=HEIGHT,
        num_frames=round(DURATION * FPS),
        frame_rate=FPS,
        steps=6,
        motion_context=motion_context,
    )
    output = OUTPUT_DIR / f"{case['name']}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(generated["video_bytes"])
    return {
        "name": case["name"],
        "verification": verify(output),
        "animation_mode": generated["parameters"].get("animation_mode"),
        "action": generated["parameters"]["motion_plan"].get("action"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=[case["name"] for case in CASES],
        default=None,
        help="Render one case instead of the full suite.",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    os.environ["LOCAL_VIDEO_RENDER_SCALE"] = "2"
    os.environ["LOCAL_VIDEO_DURATION_SECONDS"] = str(DURATION)
    os.environ["LOCAL_VIDEO_MAX_DURATION_SECONDS"] = "15"
    os.environ["LOCAL_VIDEO_JOURNEY_PAN_START"] = "0.52"
    os.environ["LOCAL_VIDEO_JOURNEY_PAN_END"] = "0.90"
    os.environ["LOCAL_VIDEO_RUN_SCALE_START"] = "0.42"
    os.environ["LOCAL_VIDEO_RUN_SCALE_END"] = "0.34"

    from hf_video_provider import generate_hf_fairytale_video

    selected_cases = [
        case for case in CASES
        if args.only is None or case["name"] == args.only
    ]
    reports = []
    for case in selected_cases:
        report = await render_case(case, generate_hf_fairytale_video)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False))
    manifest_name = (
        "male_01_nonrun_quality_v1_manifest.json"
        if args.only is None
        else f"{args.only}_manifest.json"
    )
    manifest = OUTPUT_DIR / manifest_name
    manifest.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest.resolve())


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
