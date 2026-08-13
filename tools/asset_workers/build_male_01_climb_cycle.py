"""Build the male_01 climbing sprite sheet.

The sheet is intentionally transparent. The animation assumes a wall or rock
face is supplied by the scene renderer; no climbable surface is baked into the
character asset. The source poses are reused from the existing male_01 action
sheet so the character identity, costume, scarf, and proportions stay stable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MOTION_SOURCE = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_motion_sheet_v3.png"
JUMP_SOURCE = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_jump_cycle_v19.png"
OUTPUT = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_climb_cycle_v1.png"

SHEET_COLUMNS = 4
SHEET_ROWS = 2
CELL_SIZE = (384, 512)
VISIBLE_MAX_SIZE = (360, 470)

# Existing identity-preserving poses arranged as a climbing beat. The motion
# sheet contributes the forward reach; the jump sheet contributes crouches and
# lifted knees without introducing a weapon or another character.
CLIMB_POSES = (
    ("jump", 4),
    ("motion", 6),
    ("jump", 0),
    ("motion", 6),
    ("jump", 1),
    ("motion", 6),
    ("jump", 2),
    ("jump", 7),
)


def split_sheet(sheet: Image.Image) -> list[Image.Image]:
    """Split an existing 4x2 sheet without changing its alpha channel."""
    sheet = sheet.convert("RGBA")
    cells: list[Image.Image] = []
    for row in range(SHEET_ROWS):
        top = round(row * sheet.height / SHEET_ROWS)
        bottom = round((row + 1) * sheet.height / SHEET_ROWS)
        for column in range(SHEET_COLUMNS):
            left = round(column * sheet.width / SHEET_COLUMNS)
            right = round((column + 1) * sheet.width / SHEET_COLUMNS)
            cells.append(sheet.crop((left, top, right, bottom)))
    return cells


def normalize_cell(cell: Image.Image) -> Image.Image:
    alpha = cell.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("Source pose has no visible pixels.")

    visible = cell.crop(bounds)
    scale = min(
        VISIBLE_MAX_SIZE[0] / visible.width,
        VISIBLE_MAX_SIZE[1] / visible.height,
    )
    size = (
        max(1, round(visible.width * scale)),
        max(1, round(visible.height * scale)),
    )
    visible = visible.resize(size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    left = (CELL_SIZE[0] - visible.width) // 2
    top = CELL_SIZE[1] - visible.height - 18
    canvas.alpha_composite(visible, (left, top))
    return canvas


def build_sheet(output: Path = OUTPUT) -> Path:
    with Image.open(MOTION_SOURCE) as image:
        motion_cells = split_sheet(image)
    with Image.open(JUMP_SOURCE) as image:
        jump_cells = split_sheet(image)

    source_cells = {"motion": motion_cells, "jump": jump_cells}
    cells = [
        normalize_cell(source_cells[source_name][index])
        for source_name, index in CLIMB_POSES
    ]
    sheet = Image.new(
        "RGBA",
        (CELL_SIZE[0] * SHEET_COLUMNS, CELL_SIZE[1] * SHEET_ROWS),
        (0, 0, 0, 0),
    )
    for index, cell in enumerate(cells):
        left = (index % SHEET_COLUMNS) * CELL_SIZE[0]
        top = (index // SHEET_COLUMNS) * CELL_SIZE[1]
        sheet.alpha_composite(cell, (left, top))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    return output


def validate_sheet(path: Path) -> tuple[int, int, int, bool]:
    with Image.open(path) as image:
        image.load()
        expected_size = (CELL_SIZE[0] * SHEET_COLUMNS, CELL_SIZE[1] * SHEET_ROWS)
        if image.size != expected_size:
            raise ValueError(f"Expected {expected_size}, got {image.size}.")
        if image.mode != "RGBA":
            raise ValueError(f"Expected RGBA PNG, got {image.mode}.")
        alpha = image.getchannel("A")
        if alpha.getextrema() == (255, 255):
            raise ValueError("Sheet has no transparent pixels.")
        visible_cells = 0
        for row in range(SHEET_ROWS):
            for column in range(SHEET_COLUMNS):
                box = (
                    column * CELL_SIZE[0],
                    row * CELL_SIZE[1],
                    (column + 1) * CELL_SIZE[0],
                    (row + 1) * CELL_SIZE[1],
                )
                if image.crop(box).getchannel("A").getbbox() is not None:
                    visible_cells += 1
        return image.width, image.height, visible_cells, True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    output = build_sheet(args.output)
    width, height, visible_cells, transparent = validate_sheet(output)
    print(f"Built: {output}")
    print(f"Size: {width}x{height} ({SHEET_COLUMNS}x{SHEET_ROWS}, {visible_cells} visible cells)")
    print(f"Transparent background: {transparent}")
    print("Reference: wall/rock surface is supplied by the scene; it is not embedded in the sheet.")


if __name__ == "__main__":
    main()
