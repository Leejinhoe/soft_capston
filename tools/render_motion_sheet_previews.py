import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "DB연결 테스트"
ASSET_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output" / "video_previews"

sys.path.insert(0, str(BACKEND_DIR))

from hf_video_provider import generate_hf_fairytale_video  # noqa: E402


PREVIEW_CASES = (
    {
        "name": "male_01_castle_sprite_run_v16_stride_amplified",
        "story_text": "민호가 숲길을 달려 빛나는 성을 향해 나아갔다.",
        "genre": "fantasy",
        "background": "fantasy_castle_wide_v2.png",
        "character": "male_01_reference_v2.png",
        "motion_sheet": "male_01_motion_sheet_v3.png",
        "target_journey_sheet": "male_01_target_journey_sheet_v4.png",
        "run_cycle_sheet": "male_01_run_cycle_v16.png",
        "character_key": "male_01",
        "character_pose": "walking",
        "action_tags": ["walking"],
        "background_key": "fantasy_castle",
    },
    {
        "name": "female_04_lantern_magic_v4",
        "story_text": "루나가 빛나는 등불을 들어 숲에 치유 마법을 펼쳤다.",
        "genre": "fantasy",
        "background": "nature_pond_wide_v2.png",
        "character": "female_04_reference_v2.png",
        "motion_sheet": "female_04_motion_sheet_v3.png",
        "character_key": "female_04",
        "character_pose": "casting-magic",
        "action_tags": ["casting_magic"],
        "effect_tags": ["glowing_light"],
        "background_key": "nature_pond",
    },
    {
        "name": "female_08_archer_battle_v4",
        "story_text": "솔이 활을 겨누고 다크론의 어둠 마법에 맞서 싸웠다.",
        "genre": "adventure",
        "background": "adventure_ruins_wide_v2.png",
        "character": "female_08_reference_v2.png",
        "motion_sheet": "female_08_motion_sheet_v3.png",
        "character_key": "female_08",
        "character_pose": "angry",
        "action_tags": ["fighting"],
        "background_key": "adventure_ruins",
        "secondary_character": "male_06_reference_v2.png",
        "secondary_motion_sheet": "male_06_motion_sheet_v3.png",
        "secondary_character_key": "male_06",
    },
)


async def _read_bytes(path: Path) -> bytes:
    return await asyncio.to_thread(path.read_bytes)


async def render_preview(case) -> Path:
    background_path = ASSET_DIR / "backgrounds" / case["background"]
    character_path = ASSET_DIR / "characters" / case["character"]
    motion_path = (
        ASSET_DIR / "characters" / "motion_sheets" / case["motion_sheet"]
    )
    reads = [
        _read_bytes(background_path),
        _read_bytes(character_path),
        _read_bytes(motion_path),
    ]
    secondary_character = case.get("secondary_character")
    secondary_motion_sheet = case.get("secondary_motion_sheet")
    if secondary_character:
        reads.append(
            _read_bytes(ASSET_DIR / "characters" / secondary_character)
        )
    if secondary_motion_sheet:
        reads.append(
            _read_bytes(
                ASSET_DIR
                / "characters"
                / "motion_sheets"
                / secondary_motion_sheet
            )
        )
    target_journey_sheet = case.get("target_journey_sheet")
    if target_journey_sheet:
        reads.append(
            _read_bytes(
                ASSET_DIR
                / "characters"
                / "motion_sheets"
                / target_journey_sheet
            )
        )
    run_cycle_sheet = case.get("run_cycle_sheet")
    if run_cycle_sheet:
        reads.append(
            _read_bytes(
                ASSET_DIR
                / "characters"
                / "motion_sheets"
                / run_cycle_sheet
            )
        )
    loaded = await asyncio.gather(*reads)
    background_bytes, character_bytes, motion_sheet_bytes = loaded[:3]
    cursor = 3
    secondary_character_bytes = None
    secondary_motion_sheet_bytes = None
    target_journey_sheet_bytes = None
    run_cycle_sheet_bytes = None
    if secondary_character:
        secondary_character_bytes = loaded[cursor]
        cursor += 1
    if secondary_motion_sheet:
        secondary_motion_sheet_bytes = loaded[cursor]
        cursor += 1
    if target_journey_sheet:
        target_journey_sheet_bytes = loaded[cursor]
        cursor += 1
    if run_cycle_sheet:
        run_cycle_sheet_bytes = loaded[cursor]

    generated = await generate_hf_fairytale_video(
        image_bytes=background_bytes,
        story_text=case["story_text"],
        genre=case["genre"],
        age="7",
        width=768,
        height=384,
        num_frames=240 if run_cycle_sheet else 160,
        steps=4,
        frame_rate=20,
        motion_context={
            "background_bytes": background_bytes,
            "character_bytes": character_bytes,
            "character_motion_sheet_bytes": motion_sheet_bytes,
            "character_target_journey_sheet_bytes": target_journey_sheet_bytes,
            "character_run_cycle_sheet_bytes": run_cycle_sheet_bytes,
            "character_key": case["character_key"],
            "secondary_character_bytes": secondary_character_bytes,
            "secondary_character_motion_sheet_bytes": secondary_motion_sheet_bytes,
            "secondary_character_key": case.get("secondary_character_key"),
            "character_pose": case["character_pose"],
            "action_tags": case.get("action_tags", []),
            "effect_tags": case.get("effect_tags", []),
            "background_key": case["background_key"],
        },
    )
    output_path = OUTPUT_DIR / f"{case['name']}.mp4"
    await asyncio.to_thread(output_path.write_bytes, generated["video_bytes"])
    parameters = generated["parameters"]
    print(
        f"{output_path.name}: {parameters['animation_mode']}, "
        f"{parameters['motion_plan']['action']}, "
        f"{parameters['num_frames']} frames at {parameters['frame_rate']} fps"
    )
    return output_path


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for case in PREVIEW_CASES:
        await render_preview(case)


if __name__ == "__main__":
    asyncio.run(main())
