from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "output" / "video_previews"
CASES = (
    "male_01_castle_journey",
    "female_04_lantern_magic",
    "female_08_archer_battle",
)
SAMPLE_SECONDS = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
FRAME_SIZE = (240, 135)
LABEL_HEIGHT = 24
DETAIL_SECONDS = {
    "male_01_castle_journey": (0.8, 1.0, 1.2, 3.0, 5.0, 7.0),
    "female_04_lantern_magic": (0.8, 1.8, 2.8, 4.0, 5.3, 6.8),
    "female_08_archer_battle": (0.8, 1.8, 2.7, 3.8, 5.7, 6.5),
}


def read_frame(video_path: Path, second: float, size=FRAME_SIZE) -> Image.Image:
    reader = imageio.get_reader(str(video_path))
    try:
        fps = float(reader.get_meta_data().get("fps") or 12.0)
        frame = reader.get_data(max(0, int(round(second * fps))))
    finally:
        reader.close()
    return Image.fromarray(frame).convert("RGB").resize(
        size,
        Image.Resampling.LANCZOS,
    )


def labeled_frame(video_path: Path, second: float) -> Image.Image:
    cell = Image.new(
        "RGB",
        (FRAME_SIZE[0], FRAME_SIZE[1] + LABEL_HEIGHT),
        "white",
    )
    cell.paste(read_frame(video_path, second), (0, LABEL_HEIGHT))
    ImageDraw.Draw(cell).text((8, 5), f"{second:.0f}s", fill="black")
    return cell


def compare_case(case: str) -> Path:
    old_path = VIDEO_DIR / f"{case}.mp4"
    new_path = VIDEO_DIR / f"{case}_v4.mp4"
    rows = []
    for label, path in (("v3", old_path), ("v4", new_path)):
        row = Image.new(
            "RGB",
            (FRAME_SIZE[0] * len(SAMPLE_SECONDS), FRAME_SIZE[1] + LABEL_HEIGHT),
            "#e8e8e8",
        )
        for index, second in enumerate(SAMPLE_SECONDS):
            row.paste(labeled_frame(path, second), (index * FRAME_SIZE[0], 0))
        ImageDraw.Draw(row).text((4, FRAME_SIZE[1] + 7), label, fill="#202020")
        rows.append(row)

    comparison = Image.new(
        "RGB",
        (rows[0].width, rows[0].height * len(rows)),
        "white",
    )
    for index, row in enumerate(rows):
        comparison.paste(row, (0, index * row.height))
    output_path = VIDEO_DIR / f"{case}_v3_v4_comparison.png"
    comparison.save(output_path)
    return output_path


def detail_video(video_path: Path, output_path: Path, seconds) -> Path:
    frame_size = (480, 270)
    sheet = Image.new("RGB", (frame_size[0] * 3, (frame_size[1] + 28) * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for index, second in enumerate(seconds):
        frame = read_frame(video_path, second, frame_size)
        x = (index % 3) * frame_size[0]
        y = (index // 3) * (frame_size[1] + 28)
        sheet.paste(frame, (x, y + 28))
        draw.text((x + 10, y + 7), f"{second:.1f}s", fill="black")
    sheet.save(output_path)
    return output_path


def motion_strip(video_path: Path, output_path: Path, start: float) -> Path:
    frame_size = (240, 135)
    seconds = tuple(start + index * 0.1 for index in range(10))
    sheet = Image.new("RGB", (frame_size[0] * 5, frame_size[1] * 2), "white")
    for index, second in enumerate(seconds):
        frame = read_frame(video_path, second, frame_size)
        sheet.paste(
            frame,
            ((index % 5) * frame_size[0], (index // 5) * frame_size[1]),
        )
    sheet.save(output_path)
    return output_path


def detail_case(case: str) -> Path:
    return detail_video(
        VIDEO_DIR / f"{case}_v4.mp4",
        VIDEO_DIR / f"{case}_v4_detail.png",
        DETAIL_SECONDS[case],
    )


for case_name in CASES:
    print(compare_case(case_name))
    print(detail_case(case_name))

api_video_path = VIDEO_DIR / "api_male_01_castle_run_v4_clean.mp4"
if api_video_path.exists():
    print(
        detail_video(
            api_video_path,
            VIDEO_DIR / "api_male_01_castle_run_v4_clean_detail.png",
            (0.8, 1.6, 2.4, 4.0, 5.6, 7.2),
        )
    )

target_run_path = VIDEO_DIR / "male_01_castle_target_run_v4.mp4"
if target_run_path.exists():
    print(
        detail_video(
            target_run_path,
            VIDEO_DIR / "male_01_castle_target_run_v4_detail.png",
            (0.6, 1.4, 2.4, 4.0, 5.8, 7.2),
        )
    )

sprite_run_path = VIDEO_DIR / "male_01_castle_sprite_run_v6.mp4"
if sprite_run_path.exists():
    print(
        detail_video(
            sprite_run_path,
            VIDEO_DIR / "male_01_castle_sprite_run_v6_detail.png",
            (0.5, 2.5, 4.5, 6.5, 9.0, 11.5),
        )
    )
    print(
        motion_strip(
            sprite_run_path,
            VIDEO_DIR / "male_01_castle_sprite_run_v6_motion_check.png",
            1.0,
        )
    )

api_sprite_run_path = VIDEO_DIR / "api_male_01_castle_sprite_run_v6.mp4"
if api_sprite_run_path.exists():
    print(
        detail_video(
            api_sprite_run_path,
            VIDEO_DIR / "api_male_01_castle_sprite_run_v6_detail.png",
            (0.5, 2.5, 4.5, 6.5, 9.0, 11.5),
        )
    )
    print(
        motion_strip(
            api_sprite_run_path,
            VIDEO_DIR / "api_male_01_castle_sprite_run_v6_motion_check.png",
            1.0,
        )
    )
