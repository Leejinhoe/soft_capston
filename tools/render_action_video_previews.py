"""Render a consistent preview set for the local story action animations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO_VERSION = "v29"
ACTION_ASSET_VERSION = "v28"
ACTION_ASSET_ROOT = ROOT / "output" / "action_asset_versions" / ACTION_ASSET_VERSION
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
            "partner_role": "opponent",
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
            "object_role": "golden_key",
            "subject_role": "receiver",
            "partner_role": "giver",
            "body_focus": "hands_and_gaze",
        },
    },
}

CHARACTER_KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-key", default="male_01")
    parser.add_argument(
        "--all-characters",
        action="store_true",
        help="Render the selected actions for all 16 catalog characters.",
    )
    parser.add_argument("--actions", nargs="+", choices=tuple(ACTIONS), default=list(ACTIONS))
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--asset-version",
        default=ACTION_ASSET_VERSION,
        help="Versioned jump/battle/interaction/action sheets to render.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "action_previews_v29_quality",
    )
    return parser.parse_args()


def _versioned_asset_path(character_key: str, action_name: str, version: str) -> Path:
    """Resolve the tracked canonical pack before the ignored matrix output."""

    filename = f"{character_key}_{action_name}_{version}.png"
    canonical = ROOT / "assets" / "characters" / "motion_sheets" / filename
    if version == "v28" and canonical.is_file():
        return canonical
    return ROOT / "output" / "action_asset_versions" / version / filename


async def _render_action(
    args: argparse.Namespace,
    action: str,
    character_key: str | None = None,
) -> dict:
    key = (character_key or args.character_key).strip().lower()
    character_dir = ROOT / "assets" / "characters"
    background = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
    case = ACTIONS[action]
    jump_cycle_path = _versioned_asset_path(key, "jump_cycle", args.asset_version)
    action_sheet_path = _versioned_asset_path(key, "action_sheet", args.asset_version)
    battle_cycle_path = _versioned_asset_path(key, "battle_cycle", args.asset_version)
    magic_cycle_path = character_dir / "motion_sheets" / f"{key}_magic_cycle_v22.png"
    interaction_cycle_path = _versioned_asset_path(
        key, "interaction_cycle", args.asset_version
    )
    sit_cycle_path = character_dir / "motion_sheets" / f"{key}_sit_cycle_v1.png"
    stand_cycle_path = character_dir / "motion_sheets" / f"{key}_stand_cycle_v1.png"
    action_fx_path = ROOT / "assets" / "effects" / "action_fx_sheet_v23.png"
    secondary_key = case.get("secondary_key")
    if secondary_key == key:
        secondary_key = next(candidate for candidate in CHARACTER_KEYS if candidate != key)
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
        width=960,
        height=480,
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
            "character_sit_cycle_sheet_bytes": (
                sit_cycle_path.read_bytes() if sit_cycle_path.is_file() else None
            ),
            "character_stand_cycle_sheet_bytes": (
                stand_cycle_path.read_bytes() if stand_cycle_path.is_file() else None
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
            "motion_asset_version": args.asset_version,
            # v28 sheets carry the readable action; avoid decorative overlays
            # obscuring hand/foot silhouettes during quality review. Handoff
            # keeps the semantic object layer so the transfer is visible.
            "suppress_action_effects": action != "interaction",
        },
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{key}_{action}_{VIDEO_VERSION}.mp4"
    await asyncio.to_thread(output.write_bytes, result["video_bytes"])
    manifest = {
        "path": str(output.resolve()),
        "character_key": key,
        "action": action,
        "requested_duration_seconds": args.duration,
        "requested_fps": args.fps,
        "asset_version": args.asset_version,
        "parameters": result["parameters"],
    }
    parameters = result["parameters"]
    if action in {"jump", "battle", "interaction"}:
        if parameters.get("motion_fallback_used"):
            raise RuntimeError(f"{key}/{action} unexpectedly used a motion fallback")
        if parameters.get("motion_asset_version") != args.asset_version:
            raise RuntimeError(
                f"{key}/{action} selected {parameters.get('motion_asset_version')!r}, "
                f"expected {args.asset_version!r}"
            )
    if action in {"battle", "interaction"}:
        if not parameters.get("co_star_included"):
            raise RuntimeError(f"{key}/{action} is missing its partner layer")
        if parameters.get("secondary_motion_sheet_character_key") == key:
            raise RuntimeError(f"{key}/{action} reused the primary character as partner")
    if action == "interaction":
        motion_plan = parameters.get("motion_plan") or {}
        if not motion_plan.get("requires_object"):
            raise RuntimeError("interaction preview lost its required handoff object")
    await asyncio.to_thread(
        output.with_suffix(".json").write_text,
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output.resolve())
    print(json.dumps(result["parameters"], ensure_ascii=False))
    return manifest


async def main() -> None:
    args = _parse_args()
    character_keys = list(CHARACTER_KEYS) if args.all_characters else [
        args.character_key.strip().lower()
    ]
    invalid_keys = [key for key in character_keys if key not in CHARACTER_KEYS]
    if invalid_keys:
        raise ValueError(
            "Unknown character key(s): " + ", ".join(invalid_keys)
        )
    expected_asset_names = {
        "jump": "jump_cycle",
        "battle": "battle_cycle",
        "rescue": "interaction_cycle",
        "interaction": "interaction_cycle",
    }
    missing = []
    for key in character_keys:
        for action in args.actions:
            asset_name = expected_asset_names.get(action)
            if not asset_name:
                continue
            path = _versioned_asset_path(key, asset_name, args.asset_version)
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(str(path))
    if missing:
        raise FileNotFoundError("Missing dedicated action assets:\n" + "\n".join(missing))

    reports = []
    for key in character_keys:
        for action in args.actions:
            reports.append(await _render_action(args, action, key))
    await asyncio.to_thread(
        (args.output_dir / "manifest.json").write_text,
        json.dumps(reports, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
