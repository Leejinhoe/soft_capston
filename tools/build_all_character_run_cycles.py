import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MOTION_SHEET_DIR = ROOT / "assets" / "characters" / "motion_sheets"
OUTPUT_DIR = ROOT / "output" / "video_previews"
CHARACTER_KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)
SHEET_COLUMNS = 4
SHEET_ROWS = 2
CELL_SIZE = (384, 512)
VISIBLE_MAX_SIZE = (374, 420)
BASELINE_Y = 480


def _source_path(character_key: str) -> Path:
    if character_key == "male_01":
        return MOTION_SHEET_DIR / "male_01_run_cycle_v11.png"
    return MOTION_SHEET_DIR / f"{character_key}_target_journey_sheet_v4.png"


def _split_sheet(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
    cells = []
    for row in range(SHEET_ROWS):
        top = round(row * sheet.height / SHEET_ROWS)
        bottom = round((row + 1) * sheet.height / SHEET_ROWS)
        for column in range(SHEET_COLUMNS):
            left = round(column * sheet.width / SHEET_COLUMNS)
            right = round((column + 1) * sheet.width / SHEET_COLUMNS)
            cells.append(sheet.crop((left, top, right, bottom)))
    return cells


def _remove_small_edge_fragments(cell: Image.Image) -> Image.Image:
    pixels = np.array(cell.convert("RGBA"))
    alpha_mask = (pixels[:, :, 3] > 8).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        alpha_mask,
        connectivity=8,
    )
    if count <= 2:
        return cell

    largest_area = int(stats[1:, cv2.CC_STAT_AREA].max())
    height, width = alpha_mask.shape
    for label in range(1, count):
        left = int(stats[label, cv2.CC_STAT_LEFT])
        top = int(stats[label, cv2.CC_STAT_TOP])
        component_width = int(stats[label, cv2.CC_STAT_WIDTH])
        component_height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        touches_edge = (
            left <= 1
            or top <= 1
            or left + component_width >= width - 1
            or top + component_height >= height - 1
        )
        if touches_edge and area < largest_area * 0.08:
            pixels[labels == label, 3] = 0
    return Image.fromarray(pixels, mode="RGBA")


def _visible_crop(cell: Image.Image) -> Image.Image:
    cell = _remove_small_edge_fragments(cell)
    bounds = cell.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Sprite cell has no visible pixels.")
    return cell.crop(bounds)


def _normalize_cells(cells: list[Image.Image]) -> list[Image.Image]:
    visible_cells = [_visible_crop(cell) for cell in cells]
    max_width = max(cell.width for cell in visible_cells)
    max_height = max(cell.height for cell in visible_cells)
    scale = min(
        VISIBLE_MAX_SIZE[0] / max_width,
        VISIBLE_MAX_SIZE[1] / max_height,
    )

    normalized = []
    for visible in visible_cells:
        width = max(1, round(visible.width * scale))
        height = max(1, round(visible.height * scale))
        resized = visible.resize((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
        left = (CELL_SIZE[0] - width) // 2
        top = BASELINE_Y - height
        canvas.alpha_composite(resized, (left, top))
        normalized.append(canvas)
    return normalized


def _pack_sheet(cells: list[Image.Image]) -> Image.Image:
    sheet = Image.new(
        "RGBA",
        (CELL_SIZE[0] * SHEET_COLUMNS, CELL_SIZE[1] * SHEET_ROWS),
        (0, 0, 0, 0),
    )
    for index, cell in enumerate(cells):
        left = index % SHEET_COLUMNS * CELL_SIZE[0]
        top = index // SHEET_COLUMNS * CELL_SIZE[1]
        sheet.alpha_composite(cell, (left, top))
    return sheet


def build_run_cycle_sheets(version: str) -> list[Path]:
    written = []
    for character_key in CHARACTER_KEYS:
        cells = _normalize_cells(_split_sheet(_source_path(character_key)))
        output_path = MOTION_SHEET_DIR / f"{character_key}_run_cycle_{version}.png"
        _pack_sheet(cells).save(output_path, optimize=True)
        written.append(output_path)
    return written


def _checker_cell(size: tuple[int, int]) -> Image.Image:
    cell = Image.new("RGBA", size, (38, 42, 53, 255))
    draw = ImageDraw.Draw(cell)
    tile = 12
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2 == 0:
                draw.rectangle(
                    (x, y, x + tile - 1, y + tile - 1),
                    fill=(49, 54, 67, 255),
                )
    return cell


def render_contact_sheet(
    output_path: Path,
    *,
    version: str | None = None,
) -> Path:
    frame_size = (96, 128)
    label_width = 104
    row_height = frame_size[1]
    sheet = Image.new(
        "RGB",
        (label_width + frame_size[0] * 8, row_height * len(CHARACTER_KEYS)),
        (24, 27, 35),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    checker = _checker_cell(frame_size)

    for row, character_key in enumerate(CHARACTER_KEYS):
        path = (
            MOTION_SHEET_DIR / f"{character_key}_run_cycle_{version}.png"
            if version
            else _source_path(character_key)
        )
        cells = _split_sheet(path)
        top = row * row_height
        draw.text((8, top + 54), character_key, fill=(244, 246, 252), font=font)
        for column, cell in enumerate(cells):
            preview = cell.copy()
            preview.thumbnail((88, 120), Image.Resampling.LANCZOS)
            backdrop = checker.copy()
            backdrop.alpha_composite(
                preview,
                (
                    (frame_size[0] - preview.width) // 2,
                    frame_size[1] - preview.height - 4,
                ),
            )
            sheet.paste(
                backdrop.convert("RGB"),
                (label_width + column * frame_size[0], top),
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, optimize=True)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--version", default="v12")
    parser.add_argument(
        "--contact-sheet",
        type=Path,
        default=OUTPUT_DIR / "all_character_run_cycle_sources.png",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.build:
        paths = build_run_cycle_sheets(args.version)
        print(f"Built {len(paths)} normalized run-cycle sheets ({args.version}).")
        render_contact_sheet(
            args.contact_sheet,
            version=args.version,
        )
    else:
        render_contact_sheet(args.contact_sheet)
    print(args.contact_sheet)


if __name__ == "__main__":
    main()
