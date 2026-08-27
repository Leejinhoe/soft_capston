"""Build runtime-ready identity-preserving pose sheets for one character.

The source is an image-generated 4x2 pose board. This pass removes the baked
editor checkerboard by flood-filling only connected neutral background pixels,
then repacks selected poses into the runtime 384x512 cell contract. No pose is
repainted or composited with a different character.
"""

from __future__ import annotations

import json
import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MOTION_DIR = ROOT / "assets" / "characters" / "motion_sheets"

CELL_WIDTH = 384
CELL_HEIGHT = 512
COLUMNS = 4
ROWS = 2
FRAME_COUNT = COLUMNS * ROWS
SHEET_SIZE = (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS)
GROUND_BASELINE = 480

ACTION_MAP = {
    "crawl": (1, 2, 3, 2, 3, 2, 3, 1),
    "climb": (1, 4, 5, 4, 5, 4, 5, 1),
    "sit": (0, 1, 6, 6, 6, 6, 1, 0),
    "stand": (0, 1, 0, 7, 7, 0, 1, 0),
}

PHASES = {
    "crawl": ("prepare", "act", "act", "act", "hold", "recover", "recover", "recover"),
    "climb": ("prepare", "act", "act", "act", "hold", "recover", "recover", "recover"),
    "sit": ("prepare", "lower", "lower", "contact", "hold", "hold", "recover", "recover"),
    "stand": ("prepare", "rise", "rise", "hold", "hold", "recover", "recover", "settle"),
}


def _split_sheet(sheet: Image.Image) -> list[Image.Image]:
    cells = []
    for row in range(ROWS):
        top = round(row * sheet.height / ROWS)
        bottom = round((row + 1) * sheet.height / ROWS)
        for column in range(COLUMNS):
            left = round(column * sheet.width / COLUMNS)
            right = round((column + 1) * sheet.width / COLUMNS)
            cells.append(sheet.crop((left, top, right, bottom)).convert("RGBA"))
    if len(cells) != FRAME_COUNT:
        raise ValueError(f"Expected {FRAME_COUNT} source cells, got {len(cells)}")
    return cells


def _is_checker_pixel(pixel: tuple[int, int, int, int]) -> bool:
    r, g, b, _ = pixel
    return max(r, g, b) - min(r, g, b) <= 12 and min(r, g, b) >= 225


def _remove_connected_checkerboard(cell: Image.Image) -> Image.Image:
    """Remove neutral checker pixels connected to the cell boundary only."""

    rgba = cell.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visited = bytearray(width * height)
    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))

    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if visited[index] or not _is_checker_pixel(pixels[x, y]):
            continue
        visited[index] = 1
        background[index] = 255
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
            (x - 1, y - 1),
            (x + 1, y - 1),
            (x - 1, y + 1),
            (x + 1, y + 1),
        ):
            if 0 <= nx < width and 0 <= ny < height:
                queue.append((nx, ny))

    background_mask = Image.frombytes("L", (width, height), bytes(background))
    # Remove a very small neutral fringe around the checkerboard, while leaving
    # disconnected white costume details untouched.
    expanded = background_mask.filter(ImageFilter.MaxFilter(3))
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda value: value)
    alpha = Image.composite(Image.new("L", (width, height), 0), alpha, expanded)
    rgba.putalpha(alpha)
    return _remove_edge_fragments(rgba)


def _remove_edge_fragments(cell: Image.Image) -> Image.Image:
    """Drop small colored bleed pieces that touch a generated cell edge."""

    rgba = cell.convert("RGBA")
    alpha = rgba.getchannel("A")
    width, height = alpha.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    components: list[tuple[list[int], int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or pixels[x, y] < 32:
                continue
            visited[index] = 1
            queue = [index]
            component: list[int] = []
            min_x = max_x = x
            min_y = max_y = y
            while queue:
                current = queue.pop()
                component.append(current)
                cx = current % width
                cy = current // width
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    neighbor = ny * width + nx
                    if not visited[neighbor] and pixels[nx, ny] >= 32:
                        visited[neighbor] = 1
                        queue.append(neighbor)
            components.append((component, min_x, min_y, max_x, max_y))

    if len(components) <= 1:
        return rgba
    dominant_area = max(len(component) for component, *_ in components)
    cleaned_alpha = alpha.copy()
    cleaned_pixels = cleaned_alpha.load()
    for component, min_x, min_y, max_x, max_y in components:
        touches_edge = min_x <= 1 or min_y <= 1 or max_x >= width - 2 or max_y >= height - 2
        is_small_edge_bleed = touches_edge and len(component) < dominant_area * 0.10
        if is_small_edge_bleed:
            for index in component:
                cleaned_pixels[index % width, index // width] = 0
    rgba.putalpha(cleaned_alpha)
    return rgba


def _fit_cell(cell: Image.Image) -> Image.Image:
    cleaned = _remove_connected_checkerboard(cell)
    bounds = cleaned.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Pose cell became empty after checkerboard removal")
    visible = cleaned.crop(bounds)
    scale = min(356 / visible.width, 448 / visible.height)
    size = (
        max(1, round(visible.width * scale)),
        max(1, round(visible.height * scale)),
    )
    resized = visible.resize(size, Image.Resampling.LANCZOS)
    tile = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    tile.alpha_composite(
        resized,
        ((CELL_WIDTH - resized.width) // 2, GROUND_BASELINE - resized.height),
    )
    return tile


def _pack(cells: list[Image.Image]) -> Image.Image:
    sheet = Image.new("RGBA", SHEET_SIZE, (0, 0, 0, 0))
    for index, cell in enumerate(cells):
        sheet.alpha_composite(
            cell,
            ((index % COLUMNS) * CELL_WIDTH, (index // COLUMNS) * CELL_HEIGHT),
        )
    return sheet


def _contact_sheet(character_key: str, action: str, sheet: Image.Image) -> Image.Image:
    output = Image.new("RGB", (SHEET_SIZE[0], SHEET_SIZE[1] + 54), (224, 230, 235))
    draw = ImageDraw.Draw(output)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 14), f"{character_key} / {action} / v2", fill=(35, 45, 58), font=font)
    for index in range(FRAME_COUNT):
        x = (index % COLUMNS) * CELL_WIDTH
        y = 54 + (index // COLUMNS) * CELL_HEIGHT
        checker = Image.new("RGB", (CELL_WIDTH, CELL_HEIGHT), (224, 230, 235))
        checker_draw = ImageDraw.Draw(checker)
        for cy in range(0, CELL_HEIGHT, 32):
            for cx in range(0, CELL_WIDTH, 32):
                if ((cx // 32) + (cy // 32)) % 2:
                    checker_draw.rectangle((cx, cy, cx + 31, cy + 31), fill=(238, 242, 244))
        cell = sheet.crop((x, (index // COLUMNS) * CELL_HEIGHT, x + CELL_WIDTH, (index // COLUMNS + 1) * CELL_HEIGHT))
        checker.paste(cell, mask=cell.getchannel("A"))
        output.paste(checker, (x, y))
        ImageDraw.Draw(output).text((x + 12, y + 12), f"{index + 1} {PHASES[action][index]}", fill=(35, 45, 58), font=font)
    return output


def _validate(sheet: Image.Image) -> dict[str, object]:
    if sheet.mode != "RGBA" or sheet.size != SHEET_SIZE:
        raise ValueError(f"Invalid runtime sheet: {sheet.mode} {sheet.size}")
    alpha = sheet.getchannel("A")
    cells = []
    for index in range(FRAME_COUNT):
        box = (
            index % COLUMNS * CELL_WIDTH,
            index // COLUMNS * CELL_HEIGHT,
            (index % COLUMNS + 1) * CELL_WIDTH,
            (index // COLUMNS + 1) * CELL_HEIGHT,
        )
        cell_alpha = alpha.crop(box)
        bbox = cell_alpha.getbbox()
        if bbox is None:
            raise ValueError(f"Empty runtime cell {index + 1}")
        cells.append({"cell": index + 1, "bbox": list(bbox), "visible_pixels": sum(cell_alpha.getdata())})
    return {"size": list(sheet.size), "mode": sheet.mode, "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("character_key")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    character_key = str(args.character_key).strip()
    source_path = args.source if args.source.is_absolute() else ROOT / args.source
    review_dir = ROOT / "output" / "asset_reviews" / f"{character_key}_pose_cycles_v2"
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    MOTION_DIR.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_path).convert("RGBA")
    source_cells = _split_sheet(source)
    packed_cells = [_fit_cell(cell) for cell in source_cells]
    records = []
    for action, mapping in ACTION_MAP.items():
        sheet = _pack([packed_cells[index] for index in mapping])
        validation = _validate(sheet)
        filename = f"{character_key}_{action}_cycle_v2.png"
        sheet.save(MOTION_DIR / filename, format="PNG", optimize=True)
        _contact_sheet(character_key, action, sheet).save(review_dir / f"{filename[:-4]}_contact.png", format="PNG", optimize=True)
        records.append({
            "action": action,
            "filename": f"motion_sheets/{filename}",
            "quality_tier": f"video_{action}_cycle_v2",
            "source": "imagegen_identity_reference_v1",
            "source_cells": [index + 1 for index in mapping],
            "phases": list(PHASES[action]),
            "validation": validation,
        })
    (MOTION_DIR / f"{character_key}_pose_cycles_v2_manifest.json").write_text(
        json.dumps({
            "version": "v2",
            "character_key": character_key,
            "source": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "transparent_runtime_contract": {"columns": COLUMNS, "rows": ROWS, "cell_size": [CELL_WIDTH, CELL_HEIGHT]},
            "assets": records,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Built {len(records)} pose cycles for {character_key} in {MOTION_DIR}")


if __name__ == "__main__":
    main()
