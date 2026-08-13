"""Amplify lower-body stride in an existing 4x2 run-cycle sheet."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOTION_DIR = ROOT / "assets" / "characters" / "motion_sheets"


def _split(sheet: Image.Image) -> list[Image.Image]:
    cells = []
    for row in range(2):
        for column in range(4):
            cells.append(
                sheet.crop(
                    (
                        round(column * sheet.width / 4),
                        round(row * sheet.height / 2),
                        round((column + 1) * sheet.width / 4),
                        round((row + 1) * sheet.height / 2),
                    )
                )
            )
    return cells


def _amplify(cell: Image.Image, frame_index: int, amplitude: float) -> Image.Image:
    rgba = np.asarray(cell.convert("RGBA"))
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        return cell
    top = int(ys.min())
    bottom = int(ys.max())
    hip = top + (bottom - top) * 0.58
    swing = math.sin(frame_index / 8.0 * math.pi * 2.0) * amplitude

    height, width = alpha.shape
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    weight = np.clip((grid_y - hip) / max(1.0, bottom - hip), 0.0, 1.0)
    weight = weight * weight * (3.0 - 2.0 * weight)
    map_x = grid_x - weight * swing
    map_y = grid_y
    transformed = cv2.remap(
        rgba,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    amplified = Image.fromarray(transformed, mode="RGBA")
    amplified_bounds = amplified.getchannel("A").getbbox()
    if amplified_bounds is None:
        return cell
    amplified_center = (amplified_bounds[0] + amplified_bounds[2]) / 2.0
    offset_x = round(cell.width / 2.0 - amplified_center)
    centered = Image.new("RGBA", cell.size, (0, 0, 0, 0))
    centered.alpha_composite(amplified, (offset_x, 0))
    return centered


def amplify(input_path: Path, output_path: Path, amplitude: float) -> None:
    with Image.open(input_path) as source:
        cells = _split(source.convert("RGBA"))
    result = Image.new("RGBA", (cells[0].width * 4, cells[0].height * 2))
    for index, cell in enumerate(cells):
        left = index % 4 * cell.width
        top = index // 4 * cell.height
        result.alpha_composite(_amplify(cell, index, amplitude), (left, top))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, optimize=True)
    print(output_path.resolve())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--amplitude", type=float, default=18.0)
    args = parser.parse_args()
    amplify(args.input, args.output, args.amplitude)


if __name__ == "__main__":
    main()
