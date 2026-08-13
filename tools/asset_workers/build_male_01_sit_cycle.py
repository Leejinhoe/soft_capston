"""Build a transparent 4x2 sitting-cycle sheet from existing male_01 poses.

The neutral character comes from ``male_01_motion_sheet_v3.png`` and the
coherent crouch/seated poses come from ``male_01_jump_cycle_v19.png``.  Using
complete existing cut-outs avoids repainting the face, scarf, tunic, shorts,
boots, and palette while keeping the action readable.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MOTION_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_motion_sheet_v3.png"
JUMP_SHEET = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_jump_cycle_v19.png"
OUTPUT_PATH = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_sit_cycle_v1.png"

GRID_COLUMNS = 4
GRID_ROWS = 2
TILE_SIZE = 512
GROUND_BOTTOM = 501


def _grid_cell(sheet: Image.Image, index: int) -> Image.Image:
    """Extract one cell from a 4x2 source sheet without assuming its size."""

    column = index % GRID_COLUMNS
    row = index // GRID_COLUMNS
    left = round(column * sheet.width / GRID_COLUMNS)
    right = round((column + 1) * sheet.width / GRID_COLUMNS)
    top = round(row * sheet.height / GRID_ROWS)
    bottom = round((row + 1) * sheet.height / GRID_ROWS)
    return sheet.crop((left, top, right, bottom)).convert("RGBA")


def _fit_source_cell(cell: Image.Image, *, x_shift: int = 0, y_shift: int = 0) -> Image.Image:
    """Scale a source cell to one tile and align its visible bottom edge."""

    tile = cell.resize((TILE_SIZE, TILE_SIZE), resample=Image.Resampling.LANCZOS)
    bbox = tile.getbbox()
    if bbox is None:
        raise ValueError("Source pose cell is empty")
    dx = round((TILE_SIZE / 2) - ((bbox[0] + bbox[2]) / 2)) + x_shift
    dy = GROUND_BOTTOM - bbox[3] + y_shift
    aligned = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    aligned.alpha_composite(tile, (dx, dy))
    return aligned


def _hold_variation(frame: Image.Image, x_shift: int) -> Image.Image:
    """Make a barely perceptible seated hold variation without changing identity."""

    shifted = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shifted.alpha_composite(frame, (x_shift, 0))
    return shifted


def build_sheet() -> Image.Image:
    motion_sheet = Image.open(MOTION_SHEET).convert("RGBA")
    jump_sheet = Image.open(JUMP_SHEET).convert("RGBA")

    standing = _fit_source_cell(_grid_cell(motion_sheet, 0))
    recovery = _fit_source_cell(_grid_cell(motion_sheet, 0), x_shift=2)

    # Existing complete poses: crouch -> deep crouch -> legs forward -> rise.
    # Jump frame 4 reads as a seated/legs-forward hold when grounded in a tile.
    crouch = _fit_source_cell(_grid_cell(jump_sheet, 6))
    deep_crouch = _fit_source_cell(_grid_cell(jump_sheet, 0))
    seated = _fit_source_cell(_grid_cell(jump_sheet, 4))
    seated_hold = _hold_variation(seated, 2)

    frames = (
        standing,
        crouch,
        deep_crouch,
        seated,
        seated_hold,
        seated,
        deep_crouch,
        recovery,
    )

    sheet = Image.new(
        "RGBA",
        (GRID_COLUMNS * TILE_SIZE, GRID_ROWS * TILE_SIZE),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(frames):
        x = (index % GRID_COLUMNS) * TILE_SIZE
        y = (index // GRID_COLUMNS) * TILE_SIZE
        sheet.alpha_composite(frame, (x, y))
    return sheet


def main() -> None:
    for source in (MOTION_SHEET, JUMP_SHEET):
        if not source.exists():
            raise FileNotFoundError(source)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet = build_sheet()
    sheet.save(OUTPUT_PATH, format="PNG", optimize=True)
    print(f"created {OUTPUT_PATH}")
    print(f"size={sheet.size} mode={sheet.mode} cells={GRID_COLUMNS * GRID_ROWS}")


if __name__ == "__main__":
    main()
