"""Build the male_01 stand-up motion sheet with local image warping.

The source character is kept intact and only its vertical pose is warped. This
keeps the face, costume, scarf, and palette consistent with the existing
character assets while producing a compact 4x2 runtime sprite sheet.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "assets" / "characters" / "male_01_reference_v2.png"
OUTPUT_PATH = (
    ROOT
    / "assets"
    / "characters"
    / "motion_sheets"
    / "male_01_stand_cycle_v1.png"
)

CELL_WIDTH = 384
CELL_HEIGHT = 512
COLUMNS = 4
ROWS = 2
FRAME_COUNT = COLUMNS * ROWS


def _fit_reference_to_cell(source_path: Path) -> np.ndarray:
    """Crop the transparent reference and anchor its feet in one cell."""

    with Image.open(source_path) as image:
        reference = image.convert("RGBA")

    bbox = reference.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"Reference has no visible pixels: {source_path}")

    cropped = reference.crop(bbox)
    target_height = 464
    scale = target_height / cropped.height
    target_width = max(1, round(cropped.width * scale))
    fitted = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)

    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    left = (CELL_WIDTH - target_width) // 2
    top = 22
    cell.alpha_composite(fitted, (left, top))
    return np.asarray(cell, dtype=np.uint8)


def _warp_pose(base: np.ndarray, target_landmarks: np.ndarray, *, lean: float, width_scale: float) -> np.ndarray:
    """Warp the standing reference to a pose while keeping the foot baseline."""

    source_landmarks = np.array([22, 133, 254, 338, 407, 486], dtype=np.float32)
    if target_landmarks.shape != source_landmarks.shape:
        raise ValueError("Each pose must contain six vertical landmarks")

    height, width = base.shape[:2]
    yy, xx = np.indices((height, width), dtype=np.float32)
    valid_y = (yy >= target_landmarks[0]) & (yy <= target_landmarks[-1])
    source_y = np.interp(
        yy.reshape(-1), target_landmarks, source_landmarks
    ).reshape(height, width)

    # Lean is strongest at the shoulders and fades into the grounded boots.
    progress = np.clip(
        (yy - target_landmarks[0])
        / max(1.0, target_landmarks[-1] - target_landmarks[0]),
        0.0,
        1.0,
    )
    horizontal_shift = lean * (1.0 - progress)
    source_x = (xx - (width / 2.0) - horizontal_shift) / width_scale + (width / 2.0)
    valid = valid_y & (source_x >= 0) & (source_x < width - 1)

    map_x = np.where(valid, source_x, -1).astype(np.float32)
    map_y = np.where(valid, source_y, -1).astype(np.float32)
    warped = cv2.remap(
        base,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    warped[~valid] = 0
    return warped


def build_sheet() -> Image.Image:
    base = _fit_reference_to_cell(SOURCE_PATH)

    # Top-to-bottom landmarks describe the visual phases of standing up:
    # low crouch, weight transfer, torso extension, balance, and final settle.
    poses = (
        ([112, 194, 297, 368, 427, 486], 12.0, 1.07),
        ([98, 182, 289, 362, 425, 486], 10.0, 1.06),
        ([84, 170, 280, 356, 422, 486], 8.0, 1.05),
        ([70, 157, 271, 350, 419, 486], 6.0, 1.04),
        ([56, 144, 262, 345, 416, 486], 4.0, 1.03),
        ([42, 137, 257, 341, 413, 486], 2.0, 1.02),
        ([29, 133, 254, 338, 410, 486], -1.5, 1.01),
        ([22, 133, 254, 338, 407, 486], 0.0, 1.00),
    )

    sheet = Image.new(
        "RGBA", (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS), (0, 0, 0, 0)
    )
    for index, (landmarks, lean, width_scale) in enumerate(poses):
        frame = _warp_pose(
            base,
            np.asarray(landmarks, dtype=np.float32),
            lean=lean,
            width_scale=width_scale,
        )
        frame_image = Image.fromarray(frame, mode="RGBA")
        col = index % COLUMNS
        row = index // COLUMNS
        sheet.alpha_composite(frame_image, (col * CELL_WIDTH, row * CELL_HEIGHT))
    return sheet


def validate_sheet(image: Image.Image) -> None:
    expected_size = (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS)
    if image.size != expected_size:
        raise AssertionError(f"Expected {expected_size}, got {image.size}")
    alpha = image.getchannel("A")
    for index in range(FRAME_COUNT):
        col = index % COLUMNS
        row = index // COLUMNS
        box = (
            col * CELL_WIDTH,
            row * CELL_HEIGHT,
            (col + 1) * CELL_WIDTH,
            (row + 1) * CELL_HEIGHT,
        )
        if alpha.crop(box).getbbox() is None:
            raise AssertionError(f"Frame {index + 1} is empty")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet = build_sheet()
    validate_sheet(sheet)
    sheet.save(OUTPUT_PATH, format="PNG", optimize=True)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Size: {sheet.size[0]}x{sheet.size[1]} RGBA")
    print(f"Frames: {FRAME_COUNT} ({COLUMNS}x{ROWS}), cell={CELL_WIDTH}x{CELL_HEIGHT}")


if __name__ == "__main__":
    main()
