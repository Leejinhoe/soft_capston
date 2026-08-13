import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND))

from hf_video_provider import generate_hf_fairytale_video  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a local movement preview.")
    parser.add_argument("--character-key", default="male_01")
    parser.add_argument(
        "--run-cycle-path",
        type=Path,
        default=None,
        help="Optional custom normalized 4x2 run-cycle sheet.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "output"
        / "video_previews"
        / "male_01_castle_road_run_v16_stride_amplified.mp4",
    )
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--fps", type=int, default=30)
    return parser.parse_args()


async def _render(args: argparse.Namespace) -> None:
    background = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
    character_dir = ROOT / "assets" / "characters"
    character_key = args.character_key.strip().lower()
    if not (
        character_key.startswith(("male_", "female_"))
        and character_key[-2:].isdigit()
        and 1 <= int(character_key[-2:]) <= 8
    ):
        raise ValueError("--character-key must be male_01..08 or female_01..08")
    character = character_dir / f"{character_key}_reference_v2.png"
    run_cycle = args.run_cycle_path or (
        character_dir / "motion_sheets" / f"{character_key}_run_cycle_v16.png"
    )
    frame_count = max(1, round(args.duration * args.fps))

    result = await generate_hf_fairytale_video(
        image_bytes=background.read_bytes(),
        story_text="The hero runs along the stone path toward the glowing castle.",
        genre="fantasy",
        age="7",
        width=768,
        height=384,
        num_frames=frame_count,
        frame_rate=args.fps,
        steps=2,
        motion_context={
            "background_key": "fantasy_castle",
            "background_bytes": background.read_bytes(),
            "character_key": character_key,
            "character_pose": "walking",
            "character_bytes": character.read_bytes(),
            "character_run_cycle_sheet_bytes": run_cycle.read_bytes(),
            "action_tags": ["running"],
            "motion_modifier_tags": ["fast_agile"],
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result["video_bytes"])
    print(args.output.resolve())
    print(json.dumps(result["parameters"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_render(_parse_args()))
