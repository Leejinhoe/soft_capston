import asyncio
import sys
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = next(
    path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file()
)
ASSET_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output" / "video_previews"

sys.path.insert(0, str(BACKEND_DIR))

from hf_video_provider import generate_hf_fairytale_video  # noqa: E402


ROUTE_CASES = (
    {
        "name": "fantasy_castle_route_run_v6",
        "background_key": "fantasy_castle",
        "background": "fantasy_castle_wide_v2.png",
        "character_key": "male_01",
        "story": "The young hero runs along the stone path toward the castle.",
    },
    {
        "name": "adventure_ruins_route_run_v6",
        "background_key": "adventure_ruins",
        "background": "adventure_ruins_wide_v2.png",
        "character_key": "male_02",
        "story": "The explorer runs across the bridge toward the ancient ruins.",
    },
    {
        "name": "nature_pond_route_run_v6",
        "background_key": "nature_pond",
        "background": "nature_pond_wide_v2.png",
        "character_key": "female_08",
        "story": "The forest guardian runs along the woodland path toward the grove.",
    },
    {
        "name": "friendship_square_route_run_v6",
        "background_key": "friendship_square",
        "background": "friendship_square_wide_v2.png",
        "character_key": "female_02",
        "story": "The child runs across the village square toward the pavilion.",
    },
    {
        "name": "mystery_library_route_run_v6",
        "background_key": "mystery_library",
        "background": "mystery_library_wide_v2.png",
        "character_key": "male_08",
        "story": "The young mage runs along the footprints toward the glowing door.",
    },
    {
        "name": "fantasy_crystal_cave_route_run_v7",
        "background_key": "fantasy_crystal_cave",
        "background": "fantasy_crystal_cave_wide_v1.png",
        "character_key": "male_01",
        "story": "The young hero runs through the crystal cave toward the portal.",
    },
    {
        "name": "adventure_harbor_route_run_v7",
        "background_key": "adventure_harbor",
        "background": "adventure_harbor_wide_v1.png",
        "character_key": "male_02",
        "story": "The explorer runs along the harbor path toward the waiting ship.",
    },
    {
        "name": "nature_snowfield_route_run_v7",
        "background_key": "nature_snowfield",
        "background": "nature_snowfield_wide_v1.png",
        "character_key": "female_08",
        "story": "The guardian runs along the snow trail toward the warm refuge.",
    },
    {
        "name": "friendship_festival_route_run_v7",
        "background_key": "friendship_festival",
        "background": "friendship_festival_wide_v1.png",
        "character_key": "female_02",
        "story": "The child runs through the festival square toward the pavilion.",
    },
    {
        "name": "mystery_clocktower_route_run_v7",
        "background_key": "mystery_clocktower",
        "background": "mystery_clocktower_wide_v1.png",
        "character_key": "male_08",
        "story": "The young mage runs along the clocktower walkway toward the secret door.",
    },
)


async def render_case(case) -> Path:
    character_key = case["character_key"]
    character_dir = ASSET_DIR / "characters"
    motion_dir = character_dir / "motion_sheets"
    background_bytes, character_bytes, motion_bytes, route_bytes = await asyncio.gather(
        asyncio.to_thread(
            (ASSET_DIR / "backgrounds" / case["background"]).read_bytes
        ),
        asyncio.to_thread(
            (character_dir / f"{character_key}_reference_v2.png").read_bytes
        ),
        asyncio.to_thread(
            (motion_dir / f"{character_key}_motion_sheet_v3.png").read_bytes
        ),
        asyncio.to_thread(
            (motion_dir / f"{character_key}_target_journey_sheet_v4.png").read_bytes
        ),
    )
    generated = await generate_hf_fairytale_video(
        image_bytes=background_bytes,
        story_text=case["story"],
        genre=case["background_key"],
        age="7",
        width=768,
        height=384,
        num_frames=160,
        steps=3,
        frame_rate=20,
        motion_context={
            "background_bytes": background_bytes,
            "character_bytes": character_bytes,
            "character_motion_sheet_bytes": motion_bytes,
            "character_target_journey_sheet_bytes": route_bytes,
            "character_key": character_key,
            "character_pose": "walking",
            "action_tags": ["walking"],
            "background_key": case["background_key"],
        },
    )
    output_path = OUTPUT_DIR / f"{case['name']}.mp4"
    await asyncio.to_thread(output_path.write_bytes, generated["video_bytes"])
    route = generated["parameters"]["journey_route"]
    print(
        f"{output_path.name}: {len(route['points'])} route points, "
        f"{generated['parameters']['num_frames']} frames"
    )
    return output_path


def read_frame(video_path: Path, second: float) -> Image.Image:
    reader = imageio.get_reader(str(video_path))
    try:
        fps = float(reader.get_meta_data().get("fps") or 20)
        frame = reader.get_data(int(round(second * fps)))
    finally:
        reader.close()
    return Image.fromarray(frame).convert("RGB").resize(
        (384, 192),
        Image.Resampling.LANCZOS,
    )


def render_contact(paths) -> Path:
    seconds = (0.5, 2.5, 4.5, 7.2)
    label_height = 30
    cell_width, cell_height = 384, 192
    canvas = Image.new(
        "RGB",
        (cell_width * len(seconds), (cell_height + label_height) * len(paths)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 18)
    for row, (case, path) in enumerate(zip(ROUTE_CASES, paths)):
        y = row * (cell_height + label_height)
        for column, second in enumerate(seconds):
            x = column * cell_width
            canvas.paste(read_frame(path, second), (x, y + label_height))
            draw.text(
                (x + 7, y + 5),
                f"{case['background_key']}  {second:.1f}s",
                font=font,
                fill="#101820",
            )
    output_path = OUTPUT_DIR / "background_route_previews_v7.png"
    canvas.save(output_path)
    return output_path


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for case in ROUTE_CASES:
        paths.append(await render_case(case))
    print(render_contact(paths))


if __name__ == "__main__":
    asyncio.run(main())
