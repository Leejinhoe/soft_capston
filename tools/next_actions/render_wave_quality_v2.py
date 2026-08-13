"""Render a clean, continuous wave preview for the selected male_01 character.

The source sheet has an idle pose and one raised-hand pose.  Optical-flow
interpolation supplies the lift/lower arc between them, so the preview does
not hard-cut between duplicated cells.  This remains a standalone preview and
does not change the shared provider routing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
BACKEND = next(
    path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file()
)
sys.path.insert(0, str(BACKEND))

from hf_video_provider import _optical_flow_interpolate  # noqa: E402


WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 6.4
FRAME_COUNT = round(FPS * DURATION_SECONDS)
SHEET_COLUMNS = 4
SHEET_ROWS = 2
WAVE_CYCLE_SECONDS = 2.0
OUTPUT = ROOT / "output" / "video_previews" / "male_01_wave_quality_v2.mp4"
CONTACT = ROOT / "output" / "video_previews" / "male_01_wave_quality_v2_contact.png"


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


def _fit_background(background: Image.Image) -> Image.Image:
    return background.convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def _prepare_layers(sheet: Image.Image) -> dict[int, Image.Image]:
    """Keep idle and raised-hand poses at one scale and one bottom baseline."""

    scale = 0.78
    return {
        index: _load_cell(sheet, index).resize(
            (round(sheet.width // SHEET_COLUMNS * scale), round(sheet.height // SHEET_ROWS * scale)),
            Image.Resampling.LANCZOS,
        )
        for index in (0, 1)
    }


def _smoothstep(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def _arc_pose(
    layers: dict[int, Image.Image],
    progress: float,
    *,
    cv2,
    cache: dict,
) -> Image.Image:
    """Return idle -> raised -> idle twice, with a continuous lift/lower arc."""

    phase = progress % 1.0
    # Two readable waves: lift, hold, lower, then repeat in the same cycle.
    segments = (
        (0.00, 0.12, 0, 0.0),
        (0.12, 0.30, 1, None),
        (0.30, 0.42, 2, 1.0),
        (0.42, 0.60, 3, None),
        (0.60, 0.70, 4, 0.0),
        (0.70, 0.88, 5, None),
        (0.88, 1.00, 6, 1.0),
    )
    for start, end, _, fixed in segments:
        if start <= phase <= end:
            if fixed is not None:
                amount = fixed
            elif phase < 0.30 or (0.70 <= phase < 0.88):
                amount = _smoothstep((phase - start) / (end - start))
            else:
                amount = 1.0 - _smoothstep((phase - start) / (end - start))
            return _optical_flow_interpolate(
                layers[0],
                layers[1],
                amount,
                Image=Image,
                cv2=cv2,
                np=np,
                cache=cache,
                cache_key=("wave-v2", "idle-raised"),
            )
    return layers[0]


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
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        (center_x - 70, ground_y - 8, center_x + 70, ground_y + 8),
        fill=(21, 35, 46, 72),
    )
    frame = Image.alpha_composite(frame.convert("RGBA"), shadow)
    left = round(center_x - layer.width / 2)
    top = ground_y - bbox[3]
    frame.alpha_composite(layer, (left, top))
    return frame.convert("RGB")


def _render_frame(
    background: Image.Image,
    layers: dict[int, Image.Image],
    index: int,
    *,
    cv2,
    cache: dict,
) -> np.ndarray:
    progress = ((index / FPS) % WAVE_CYCLE_SECONDS) / WAVE_CYCLE_SECONDS
    layer = _arc_pose(layers, progress, cv2=cv2, cache=cache)
    return np.asarray(_paste_grounded_character(background.copy(), layer), dtype=np.uint8)


def _write_video(background: Image.Image, layers: dict[int, Image.Image], output: Path) -> None:
    import cv2

    output.parent.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
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
            writer.append_data(
                _render_frame(background, layers, index, cv2=cv2, cache=cache)
            )
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
        "motion": "optical-flow continuous idle-to-raised-hand arc",
    }
    if tuple(report["resolution"]) != (WIDTH, HEIGHT) or report["frame_count"] != FRAME_COUNT:
        raise RuntimeError(f"Unexpected video metadata: {report}")
    if abs(report["fps"] - FPS) > 0.01:
        raise RuntimeError(f"Unexpected FPS: {report}")
    return report, samples


def _write_contact_sheet(samples: list[np.ndarray], contact: Path) -> None:
    tile_width = 240
    tile_height = round(tile_width * HEIGHT / WIDTH)
    label_height = 24
    columns = 4
    rows = 3
    sheet = Image.new("RGB", (tile_width * columns, (tile_height + label_height) * rows), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, frame in enumerate(samples):
        tile = Image.fromarray(frame).convert("RGB").resize(
            (tile_width, tile_height), Image.Resampling.LANCZOS
        )
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + label_height)
        sheet.paste(tile, (x, y + label_height))
        draw.text((x + 7, y + 5), f"{index * (DURATION_SECONDS / 11):.2f}s", fill=(25, 30, 35), font=font)
    contact.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact)


def main() -> None:
    args = _parse_args()
    background_path = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"
    sheet_path = ROOT / "assets" / "characters" / "motion_sheets" / "male_01_action_sheet_v21.png"
    for path in (background_path, sheet_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    with Image.open(background_path) as source:
        background = _fit_background(source)
    with Image.open(sheet_path) as source:
        layers = _prepare_layers(source)
    _write_video(background, layers, args.output)
    report, samples = _read_video_report(args.output)
    _write_contact_sheet(samples, args.contact)
    print(json.dumps({"video": report, "contact": str(args.contact.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
