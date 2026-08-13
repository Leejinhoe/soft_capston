"""Build a transparent 4x2 crawl-cycle sheet for male_01.

The source character is kept intact and reused from the existing run-cycle
sheet.  Local PIL transforms provide a low, forward-facing crawl silhouette
without introducing a new character design or an external model dependency.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL import ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_run_cycle_v16.png"
OUTPUT = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_crawl_cycle_v1.png"

GRID_COLUMNS = 4
GRID_ROWS = 2
CELL_SIZE = (384, 512)
SHEET_SIZE = (CELL_SIZE[0] * GRID_COLUMNS, CELL_SIZE[1] * GRID_ROWS)


def _source_frame(sheet: Image.Image, index: int) -> Image.Image:
    """Return one trimmed RGBA source frame while preserving its identity."""

    column = index % GRID_COLUMNS
    row = index // GRID_COLUMNS
    left = column * CELL_SIZE[0]
    top = row * CELL_SIZE[1]
    frame = sheet.crop((left, top, left + CELL_SIZE[0], top + CELL_SIZE[1])).convert("RGBA")
    bbox = frame.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"Source frame {index} has no visible pixels")
    return frame.crop(bbox)


def _crawl_pose(source: Image.Image, index: int) -> Image.Image:
    """Turn a running identity frame into one low, forward-facing crawl pose.

    The source faces right. A clockwise rotation puts the head and gaze toward
    the right while keeping the scarf, hair, clothes, and face pixels intact.
    Alternating angles and vertical offsets create the hand/knee weight shift
    that distinguishes the eight frames instead of duplicating one pose.
    """

    # The two phases alternate the leading hand/knee.  The small asymmetry keeps
    # the cycle readable while avoiding a mechanical identical-pose loop.
    angles = (-54, -60, -56, -62, -54, -60, -56, -62)
    vertical_offsets = (3, -1, -4, 0, 3, -1, -4, 0)
    horizontal_offsets = (-6, 2, 7, 1, -6, 2, 7, 1)

    def trim(image: Image.Image) -> Image.Image:
        bbox = image.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"Transformed frame {index} has no visible pixels")
        return image.crop(bbox)

    def fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
        scale = min(max_width / image.width, max_height / image.height)
        return image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            resample=Image.Resampling.LANCZOS,
        )

    # Split at the shorts/hip line before transforming.  The upper layer gives
    # the crawl its forward-facing head and planted forearm; the lower layer is
    # folded underneath the hips so the boots read as knees rather than a jump.
    width, height = source.size
    upper = source.crop((0, 0, width, round(height * 0.73)))
    lower = source.crop((0, round(height * 0.40), width, height))
    upper = trim(upper.rotate(angles[index], resample=Image.Resampling.BICUBIC, expand=True))
    lower = trim(lower.rotate(-24 + (index % 2) * 7, resample=Image.Resampling.BICUBIC, expand=True))
    upper = fit(upper, 292, 184)
    lower = fit(lower, 208, 138)

    pose = Image.new("RGBA", (350, 270), (0, 0, 0, 0))
    # Alternate which knee sits forward and which forearm reaches first.
    lower_x = (18, 26, 36, 24, 18, 26, 36, 24)[index]
    lower_y = (111, 117, 121, 115, 111, 117, 121, 115)[index]
    pose.alpha_composite(lower, (lower_x, lower_y))
    pose.alpha_composite(upper, (72 + (index % 2) * 5, 45 + (index % 3) * 3))
    pose = trim(pose)
    pose = fit(pose, 330, 230)

    canvas = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    # A very subtle alpha-only contact shadow grounds the hands and knees while
    # keeping the sheet fully transparent everywhere else.
    shadow = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (250, 22), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).ellipse((8, 3, 242, 19), fill=(30, 34, 44, 48))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(4))
    shadow.alpha_composite(shadow_layer, ((CELL_SIZE[0] - 250) // 2, 438))
    canvas.alpha_composite(shadow)
    x = (CELL_SIZE[0] - pose.width) // 2 + horizontal_offsets[index]
    baseline = 431 + vertical_offsets[index]
    y = baseline - pose.height
    canvas.alpha_composite(pose, (x, y))
    return canvas


def build_sheet() -> Image.Image:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing identity source: {SOURCE}")

    source_sheet = Image.open(SOURCE).convert("RGBA")
    if source_sheet.size != SHEET_SIZE:
        raise ValueError(
            f"Expected source size {SHEET_SIZE}, got {source_sheet.size}"
        )

    output = Image.new("RGBA", SHEET_SIZE, (0, 0, 0, 0))
    for index in range(GRID_COLUMNS * GRID_ROWS):
        frame = _crawl_pose(_source_frame(source_sheet, index), index)
        column = index % GRID_COLUMNS
        row = index // GRID_COLUMNS
        output.alpha_composite(frame, (column * CELL_SIZE[0], row * CELL_SIZE[1]))
    return output


def validate_sheet(sheet: Image.Image) -> None:
    if sheet.size != SHEET_SIZE or sheet.mode != "RGBA":
        raise AssertionError(f"Expected RGBA {SHEET_SIZE}, got {sheet.mode} {sheet.size}")
    for index in range(GRID_COLUMNS * GRID_ROWS):
        column = index % GRID_COLUMNS
        row = index // GRID_COLUMNS
        cell = sheet.crop(
            (
                column * CELL_SIZE[0],
                row * CELL_SIZE[1],
                (column + 1) * CELL_SIZE[0],
                (row + 1) * CELL_SIZE[1],
            )
        )
        if cell.getchannel("A").getbbox() is None:
            raise AssertionError(f"Cell {index} is empty")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sheet = build_sheet()
    validate_sheet(sheet)
    sheet.save(OUTPUT, format="PNG", optimize=True)

    with Image.open(OUTPUT) as written:
        validate_sheet(written.convert("RGBA"))
        print(f"created: {OUTPUT}")
        print(f"size: {written.size[0]}x{written.size[1]}")
        print(f"grid: {GRID_COLUMNS}x{GRID_ROWS} ({GRID_COLUMNS * GRID_ROWS} cells)")
        print(f"mode: {written.mode}")
        print("validation: passed")


if __name__ == "__main__":
    main()
