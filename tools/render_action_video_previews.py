"""Render a consistent preview set for the local story action animations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "DB\uc5f0\uacb0 \ud14c\uc2a4\ud2b8"
sys.path.insert(0, str(BACKEND))

from hf_video_provider import generate_hf_fairytale_video  # noqa: E402


ACTIONS = {
    "run": {
        "story_text": "The hero runs along the road toward the glowing castle.",
        "pose": "walking",
        "tags": ["running"],
        "modifiers": ["fast_agile"],
        "semantics": {"motion_mode": "locomotion", "animation_action": "journey", "pace": "run"},
    },
    "walk": {
        "story_text": "The hero walks carefully along the road toward the glowing castle.",
        "pose": "walking",
        "tags": ["walking"],
        "modifiers": ["slow_subtle"],
        "semantics": {"motion_mode": "locomotion", "animation_action": "journey", "pace": "walk"},
    },
    "jump": {
        "story_text": "The hero jumps over a fallen branch on the road.",
        "pose": "walking",
        "tags": ["jumping"],
        "modifiers": ["sudden"],
        "semantics": {"motion_mode": "stationary", "animation_action": "jump", "body_focus": "whole_body"},
    },
    "wave": {
        "story_text": "The hero waves toward the glowing castle.",
        "pose": "talking",
        "tags": ["waving"],
        "modifiers": ["smiling"],
        "semantics": {"motion_mode": "stationary", "animation_action": "wave", "body_focus": "arms_and_gaze"},
    },
    "magic": {
        "story_text": "The hero raises a hand and casts a glowing spell.",
        "pose": "magic",
        "tags": ["magic"],
        "modifiers": ["continuous"],
        "semantics": {"motion_mode": "stationary", "animation_action": "magic", "body_focus": "arms_and_gaze"},
    },
    "investigate": {
        "story_text": "The hero studies a glowing clue beside the castle road.",
        "pose": "talking",
        "tags": ["investigating"],
        "modifiers": ["thinking"],
        "semantics": {"motion_mode": "stationary", "animation_action": "investigate", "body_focus": "gaze_and_hands"},
    },
    "sit": {
        "story_text": "The hero slowly sits down beside the castle road.",
        "pose": "default",
        "tags": ["sitting"],
        "modifiers": ["slow_subtle"],
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "sit",
            "participant_count": 1,
            "body_focus": "whole_body",
        },
    },
    "stand": {
        "story_text": "The hero rises from a seated position and stands steadily.",
        "pose": "default",
        "tags": ["standing"],
        "modifiers": ["slow_subtle"],
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "stand",
            "participant_count": 1,
            "body_focus": "whole_body",
        },
    },
    "battle": {
        "story_text": "The hero steps forward and swings his sword to stop an opponent.",
        "pose": "angry",
        "tags": ["fighting"],
        "modifiers": ["sudden"],
        "secondary_key": "male_06",
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "battle",
            "participant_count": 2,
            "requires_partner": True,
            "body_focus": "whole_body",
        },
    },
    "rescue": {
        "story_text": "The hero reaches out and helps a friend stand safely.",
        "pose": "rescue",
        "tags": ["helping"],
        "modifiers": ["continuous"],
        "secondary_key": "female_03",
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "rescue",
            "participant_count": 2,
            "requires_partner": True,
            "body_focus": "arms_and_gaze",
        },
    },
    "interaction": {
        "story_text": "A friend carefully hands the hero a small golden key.",
        "pose": "talking",
        "tags": ["interacting"],
        "modifiers": ["slow_subtle"],
        "secondary_key": "female_02",
        "semantics": {
            "motion_mode": "stationary",
            "animation_action": "interaction",
            "interaction_kind": "handoff_receive",
            "participant_count": 2,
            "requires_partner": True,
            "requires_object": True,
            "body_focus": "hands_and_gaze",
        },
    },
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-key", default="male_01")
    parser.add_argument("--actions", nargs="+", choices=tuple(ACTIONS), default=list(ACTIONS))
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "action_previews",
    )
    return parser.parse_args()


async def _render_action(args: argparse.Namespace, action: str) -> Path:
    key = args.character_key.strip().lower()
    character_dir = ROOT / "assets" / "characters"
    background = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
    case = ACTIONS[action]
    jump_cycle_path = (
        character_dir / "motion_sheets" / f"{key}_jump_cycle_v19.png"
    )
    action_sheet_path = (
        character_dir / "motion_sheets" / f"{key}_action_sheet_v21.png"
    )
    battle_cycle_path = character_dir / "motion_sheets" / f"{key}_battle_cycle_v22.png"
    magic_cycle_path = character_dir / "motion_sheets" / f"{key}_magic_cycle_v22.png"
    interaction_cycle_path = (
        character_dir / "motion_sheets" / f"{key}_interaction_cycle_v22.png"
    )
    action_fx_path = ROOT / "assets" / "effects" / "action_fx_sheet_v23.png"
    secondary_key = case.get("secondary_key")
    secondary_bytes = (
        (character_dir / f"{secondary_key}_reference_v2.png").read_bytes()
        if secondary_key else None
    )
    secondary_motion_bytes = (
        (
            character_dir
            / "motion_sheets"
            / f"{secondary_key}_motion_sheet_v3.png"
        ).read_bytes()
        if secondary_key else None
    )
    result = await generate_hf_fairytale_video(
        image_bytes=background.read_bytes(),
        story_text=case["story_text"],
        genre="fantasy",
        age="7",
        width=768,
        height=384,
        num_frames=max(1, round(args.duration * args.fps)),
        frame_rate=args.fps,
        steps=2,
        motion_context={
            "background_key": "fantasy_castle",
            "background_bytes": background.read_bytes(),
            "character_key": key,
            "character_pose": case["pose"],
            "character_bytes": (character_dir / f"{key}_reference_v2.png").read_bytes(),
            "character_motion_sheet_bytes": (
                character_dir / "motion_sheets" / f"{key}_motion_sheet_v3.png"
            ).read_bytes(),
            "character_run_cycle_sheet_bytes": (
                character_dir / "motion_sheets" / f"{key}_run_cycle_v16.png"
            ).read_bytes(),
            "character_jump_cycle_sheet_bytes": (
                jump_cycle_path.read_bytes()
                if jump_cycle_path.is_file()
                else None
            ),
            "character_action_sheet_bytes": (
                action_sheet_path.read_bytes()
                if action_sheet_path.is_file()
                else None
            ),
            "character_battle_cycle_sheet_bytes": (
                battle_cycle_path.read_bytes() if battle_cycle_path.is_file() else None
            ),
            "character_magic_cycle_sheet_bytes": (
                magic_cycle_path.read_bytes() if magic_cycle_path.is_file() else None
            ),
            "character_interaction_cycle_sheet_bytes": (
                interaction_cycle_path.read_bytes()
                if interaction_cycle_path.is_file() else None
            ),
            "action_fx_sheet_bytes": (
                action_fx_path.read_bytes() if action_fx_path.is_file() else None
            ),
            "secondary_character_key": secondary_key,
            "secondary_character_bytes": secondary_bytes,
            "secondary_character_motion_sheet_bytes": secondary_motion_bytes,
            "action_tags": case["tags"],
            "motion_modifier_tags": case["modifiers"],
            "action_semantics": case["semantics"],
            "motion_focus": "character",
        },
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{key}_{action}_v25.mp4"
    await asyncio.to_thread(output.write_bytes, result["video_bytes"])
    print(output.resolve())
    print(json.dumps(result["parameters"], ensure_ascii=False))
    return output


async def main() -> None:
    args = _parse_args()
    if not (
        args.character_key.startswith(("male_", "female_"))
        and args.character_key[-2:].isdigit()
        and 1 <= int(args.character_key[-2:]) <= 8
    ):
        raise ValueError("--character-key must be male_01..08 or female_01..08")
    for action in args.actions:
        await _render_action(args, action)


if __name__ == "__main__":
    asyncio.run(main())
