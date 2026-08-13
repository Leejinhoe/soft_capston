"""Render a stable, readable male_01 wave preview from the action sheet.

This is intentionally self-contained.  It does not depend on the shared video
provider, whose action-sheet routing may vary while wave is being iterated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "assets"
CHARACTER_KEY = "male_01"
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 6.4
FRAME_COUNT = round(FPS * DURATION_SECONDS)
SHEET_COLUMNS = 4
SHEET_ROWS = 2
WAVE_CYCLE_SECONDS = 1.6
OUTPUT = ROOT / "output" / "video_previews" / "male_01_wave_quality_v1.mp4"
CONTACT = ROOT / "output" / "video_previews" / "male_01_wave_quality_v1_contact.png"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--contact", type=Path, default=CONTACT)
    return parser.parse_args()


def _load_cell(sheet: Image.Image, index: int) -> Image.Image:
    cell_width = sheet.width // SHEET_COLUMNS
    cell_height = sheet.height // SHEET_ROWS
    column = index % SHEET_COLUMNS
    row = index // SHEET_COLUMNS
    cell = sheet.crop(
        (
            column * cell_width,
            row * cell_height,
            (column + 1) * cell_width,
            (row + 1) * cell_height,
        )
    ).convert("RGBA")
    if cell.getbbox() is None:
        raise ValueError(f"Action-sheet cell {index} is empty.")
    return cell


def _select_wave_cell(progress: float) -> int:
    """Use the established action-sheet wave arc, repeated on a steady beat."""

    timeline = (
        (0.00, 0),
        (0.18, 0),
        (0.26, 1),
        (0.48, 1),
        (0.56, 0),
        (0.64, 1),
        (0.82, 1),
        (0.90, 0),
        (1.00, 0),
    )
    for end, cell_index in timeline:
        if progress <= end:
            return cell_index
    return 0


def _fit_background(background: Image.Image) -> Image.Image:
    return background.convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _prepare_character_layers(sheet: Image.Image) -> dict[int, Image.Image]:
    """Scale both poses identically and align their visible feet to one baseline."""

    cells = {index: _load_cell(sheet, index) for index in (0, 1)}
    scale = 0.78
    layers: dict[int, Image.Image] = {}
    for index, cell in cells.items():
        layers[index] = cell.resize(
            (round(cell.width * scale), round(cell.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return layers


def _paste_grounded_character(
    frame: Image.Image,
    layer: Image.Image,
    *,
    center_x: int = 570,
    ground_y: int = 446,
) -> Image.Image:
    alpha = layer.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Character layer has no visible pixels.")

    # A fixed shadow makes the common foot line legible without moving the body.
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (center_x - 70, ground_y - 8, center_x + 70, ground_y + 8),
        fill=(21, 35, 46, 72),
    )
    frame = Image.alpha_composite(frame.convert("RGBA"), shadow)

    visible_bottom = bbox[3]
    left = round(center_x - layer.width / 2)
    top = ground_y - visible_bottom
    frame.alpha_composite(layer, (left, top))
    return frame.convert("RGB")


def _render_frame(background: Image.Image, layers: dict[int, Image.Image], index: int) -> np.ndarray:
    seconds = index / FPS
    cycle_progress = (seconds % WAVE_CYCLE_SECONDS) / WAVE_CYCLE_SECONDS
    cell_index = _select_wave_cell(cycle_progress)
    frame = _paste_grounded_character(background.copy(), layers[cell_index])
    return np.asarray(frame, dtype=np.uint8)


def _write_video(background: Image.Image, layers: dict[int, Image.Image], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(output),
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=2,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for index in range(FRAME_COUNT):
            writer.append_data(_render_frame(background, layers, index))
    finally:
        writer.close()


def _read_video_report(output: Path) -> tuple[dict, list[np.ndarray]]:
    reader = imageio.get_reader(str(output))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
        sample_indices = np.linspace(0, frame_count - 1, 12, dtype=int)
        samples = [reader.get_data(int(index)) for index in sample_indices]
    finally:
        reader.close()

    fps = float(metadata.get("fps") or 0.0)
    report = {
        "path": str(output.resolve()),
        "resolution": list(metadata.get("size") or ()),
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "codec": metadata.get("codec", "h264"),
    }
    if tuple(report["resolution"]) != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution: {report}")
    if report["frame_count"] != FRAME_COUNT:
        raise RuntimeError(f"Unexpected frame count: {report}")
    if abs(report["fps"] - FPS) > 0.01:
        raise RuntimeError(f"Unexpected FPS: {report}")
    return report, samples


def _write_contact_sheet(samples: list[np.ndarray], contact: Path) -> None:
    tile_width = 240
    tile_height = round(tile_width * HEIGHT / WIDTH)
    label_height = 24
    columns = 4
    rows = 3
    sheet = Image.new(
        "RGB",
        (tile_width * columns, (tile_height + label_height) * rows),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for index, frame in enumerate(samples):
        tile = Image.fromarray(frame).convert("RGB").resize(
            (tile_width, tile_height), Image.Resampling.LANCZOS
        )
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + label_height)
        sheet.paste(tile, (x, y + label_height))
        draw.text(
            (x + 7, y + 5),
            f"{index * (DURATION_SECONDS / 11):.2f}s",
            fill=(25, 30, 35),
            font=font,
        )
    contact.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact)


def main() -> None:
    args = _parse_args()
    if args.output.name != "male_01_wave_quality_v1.mp4":
        raise ValueError("This quality renderer is locked to the male_01 output name.")
    character_dir = ASSET_DIR / "characters"
    background_path = ASSET_DIR / "backgrounds" / "fantasy_castle_wide_v2.png"
    sheet_path = character_dir / "motion_sheets" / "male_01_action_sheet_v21.png"
    for path in (background_path, sheet_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    with Image.open(background_path) as background_source:
        background = _fit_background(background_source)
    with Image.open(sheet_path) as sheet_source:
        layers = _prepare_character_layers(sheet_source)

    _write_video(background, layers, args.output)
    report, samples = _read_video_report(args.output)
    _write_contact_sheet(samples, args.contact)
    print(json.dumps({"video": report, "contact": str(args.contact.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
