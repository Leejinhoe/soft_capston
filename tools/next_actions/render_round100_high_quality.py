"""Render the round100 assets with a storybook-oriented compositing pass.

The first round100 renderer blended entire, materially different character
silhouettes. This pass preserves the authored cell coordinate system, uses
short blends only for close silhouettes, hard-cuts large pose changes, and
adds independent scene and partner layers where the vocabulary requires them.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import build_round100_pack as base


ROOT = base.ROOT
CATALOG_PATH = ROOT / "tools" / "next_actions" / "round100_catalog.json"
OUTPUT_ROOT = ROOT / "output" / "video_final" / "generated_round100_hq"
MANIFEST_PATH = ROOT / "tools" / "next_actions" / "round100_hq_manifest.json"

WIDTH, HEIGHT = 960, 480
FPS = 30
FRAME_COUNT = 240
GROUND_Y = 430
GRID_SIZE = (448, 512)
CHARACTER_SCALE = 0.82

HQ_BLENDS = {"stand", "sit", "crouch", "stretch", "yawn", "salute", "nod", "smile"}
AIR_ACTIONS = {"jump", "vault_over", "dive", "throw", "dodge", "battle", "shoot_bow", "fall_roll"}
LOW_ACTIONS = {"sit", "kneel", "crouch", "prone", "crawl", "slide", "fall_roll", "duck_under"}
TRAVEL_ACTIONS = {"journey", "walk", "run", "crawl", "climb", "slide", "cross_bridge", "squeeze_through", "duck_under", "wade", "row", "weave_through", "swim", "vault_over", "clamber_over", "dive", "stop"}

PARTNER_SHEET_CANDIDATES = (
    ROOT / "assets" / "characters" / "motion_sheets" / "female_01_motion_sheet_v3.png",
    ROOT / "assets" / "characters" / "motion_sheets" / "male_06_motion_sheet_v3.png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def read_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def normalize_cell(cell: Image.Image) -> Image.Image:
    """Normalize the full cell, rather than scaling each alpha bbox independently."""

    return cell.convert("RGBA").resize(GRID_SIZE, Image.Resampling.LANCZOS)


def load_cells(path: Path) -> list[Image.Image]:
    return [normalize_cell(cell) for cell in base.extract_source_cells(path)]


def alpha_mask(image: Image.Image) -> np.ndarray:
    return np.asarray(image.getchannel("A"), dtype=np.uint8) >= 48


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    first_mask = alpha_mask(first)
    second_mask = alpha_mask(second)
    union = np.logical_or(first_mask, second_mask).sum()
    return float(np.logical_and(first_mask, second_mask).sum() / union) if union else 0.0


def premultiplied_blend(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    value = min(max(amount, 0.0), 1.0)
    value = value * value * (3.0 - 2.0 * value)
    a = np.asarray(first, dtype=np.float32) / 255.0
    b = np.asarray(second, dtype=np.float32) / 255.0
    aa, ba = a[..., 3:4], b[..., 3:4]
    a[..., :3] *= aa
    b[..., :3] *= ba
    rgb = a[..., :3] * (1 - value) + b[..., :3] * value
    alpha = aa * (1 - value) + ba * value
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    return Image.fromarray(np.clip(np.concatenate((rgb, alpha), axis=-1) * 255, 0, 255).astype(np.uint8), "RGBA")


def pose_at(cells: list[Image.Image], progress: float, *, hard_cut: bool) -> tuple[Image.Image, int, str]:
    points = (0.0, 0.11, 0.24, 0.38, 0.54, 0.67, 0.84, 1.0)
    phases = ("prepare", "prepare", "act", "act", "hold", "hold", "recover", "recover")
    value = min(max(progress, 0.0), 1.0)
    for index in range(len(points) - 1):
        if value <= points[index + 1] or index == len(points) - 2:
            start, end = points[index], points[index + 1]
            local = (value - start) / max(0.001, end - start)
            first = cells[index]
            second = cells[index + 1]
            iou = alpha_iou(first, second)
            use_cut = hard_cut or iou < 0.72
            if use_cut:
                image = first if local < 0.52 else second
            else:
                # Keep blends short; most of the segment is a readable hold.
                blend_amount = min(max((local - 0.32) / 0.36, 0.0), 1.0)
                image = premultiplied_blend(first, second, blend_amount)
            return image, index, phases[index]
    return cells[-1], 7, "recover"


def font(size: int = 15) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def fit_background_source(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source = source.convert("RGB")
        scale = max(WIDTH / source.width, HEIGHT / source.height)
        resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
        return resized.convert("RGBA")


def background_frame(source: Image.Image, progress: float, *, moving: bool) -> Image.Image:
    if source.width < WIDTH or source.height < HEIGHT:
        scale = max(WIDTH / source.width, HEIGHT / source.height)
        source = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    max_left = max(0, source.width - WIDTH)
    if moving:
        left = round(max_left * min(max(progress, 0.0), 1.0))
    else:
        # A very small storybook camera drift keeps a static scene alive.
        left = round(max_left * (0.48 + 0.04 * math.sin(progress * math.pi * 2)))
    top = max(0, (source.height - HEIGHT) // 2)
    return source.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGBA")


def scene_layer(key: str, progress: float) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    # These objects belong to the scene, not the character pose. They remain
    # fixed while the character moves through the frame.
    if key == "cross_bridge":
        draw.polygon([(220, 430), (740, 430), (670, 350), (285, 350)], fill=(121, 78, 48, 230), outline=(58, 41, 31, 255))
        draw.polygon([(220, 430), (740, 430), (800, 480), (150, 480)], fill=(64, 133, 168, 150))
        for x in range(270, 730, 70):
            draw.line((x, 368, x + 28, 430), fill=(194, 136, 74, 255), width=8)
    elif key in {"duck_under", "squeeze_through"}:
        draw.rounded_rectangle((260, 160, 780, 218), radius=22, fill=(108, 70, 44, 255), outline=(57, 39, 28, 255), width=6)
        draw.line((295, 190, 745, 190), fill=(177, 124, 66, 255), width=8)
    elif key in {"weave_through", "clamber_over"}:
        for x, y in ((170, 210), (350, 160), (710, 195)):
            draw.rectangle((x, y, x + 36, 432), fill=(83, 105, 62, 220))
            draw.ellipse((x - 64, y - 35, x + 94, y + 80), fill=(66, 128, 74, 190))
    elif key in {"wade", "swim", "dive"}:
        draw.rectangle((0, 372, WIDTH, HEIGHT), fill=(46, 137, 178, 110))
        for x in range(100, WIDTH, 150):
            draw.arc((x, 390, x + 100, 428), 180, 350, fill=(186, 234, 244, 210), width=4)
    elif key == "row":
        draw.ellipse((290, 348, 690, 455), fill=(108, 72, 44, 255), outline=(52, 37, 29, 255), width=6)
        draw.line((370, 344, 240, 250), fill=(179, 122, 65, 255), width=9)
        draw.line((590, 344, 720, 250), fill=(179, 122, 65, 255), width=9)
    elif key in {"protect", "warn", "rescue", "dodge", "block"}:
        draw.ellipse((738, 285, 812, 359), fill=(167, 61, 65, 200), outline=(255, 211, 127, 230), width=5)
        draw.line((775, 270, 775, 374), fill=(255, 211, 127, 220), width=5)
        draw.line((732, 322, 818, 322), fill=(255, 211, 127, 220), width=5)
    return layer


def shadow_layer(key: str, x: int, pose: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    if key in AIR_ACTIONS:
        opacity = 38
        y = GROUND_Y + 4
    elif key in LOW_ACTIONS:
        opacity = 76
        y = GROUND_Y - 2
    else:
        opacity = 92
        y = GROUND_Y + 3
    width = 142 if key not in {"prone", "fall_roll"} else 190
    draw.ellipse((x - width, y - 9, x + width, y + 13), fill=(24, 31, 41, opacity))
    return layer


def partner_source() -> Path | None:
    return next((path for path in PARTNER_SHEET_CANDIDATES if path.is_file()), None)


def partner_pose(cells: list[Image.Image], progress: float) -> Image.Image:
    index = 0 if progress < 0.54 else 7
    return cells[index]


def compose_partner(frame: Image.Image, cells: list[Image.Image], key: str, progress: float) -> None:
    # Independent actor track for all partner-required words.
    partner = partner_pose(cells, progress)
    partner = partner.resize((round(GRID_SIZE[0] * CHARACTER_SCALE), round(GRID_SIZE[1] * CHARACTER_SCALE)), Image.Resampling.LANCZOS)
    if key in {"shoulder_link", "shake_hands", "present_gift", "apologize", "talk"}:
        x = 680
    elif key in {"protect", "rescue", "warn", "catch", "release"}:
        x = 690
    else:
        x = 700
    y = GROUND_Y - partner.height
    frame.alpha_composite(partner, (x - partner.width // 2, y))


def action_position(key: str, progress: float) -> int:
    if key in TRAVEL_ACTIONS:
        return 480
    if key in {"present_gift", "shoulder_link", "shake_hands", "talk", "apologize", "beckon"}:
        return 360
    if key in {"protect", "rescue", "warn", "catch", "release"}:
        return round(360 + 110 * min(max(progress, 0.0), 1.0))
    return 480


def render_record(record: dict[str, Any], background_cache: dict[str, Image.Image], partner_cells: list[Image.Image] | None, output_path: Path) -> dict[str, Any]:
    key = record["key"]
    cells = load_cells(Path(record["motion_sheet_path"]))
    hard_cut = record.get("asset_kind") == "generated_composite" or key not in HQ_BLENDS
    moving = key in TRAVEL_ACTIONS
    background = background_cache[record["group"]]
    with imageio.get_writer(str(output_path), fps=FPS, codec="libx264", quality=8, ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]) as writer:
        for frame_index in range(FRAME_COUNT):
            progress = frame_index / max(1, FRAME_COUNT - 1)
            frame = background_frame(background, progress, moving=moving)
            frame.alpha_composite(scene_layer(key, progress))
            pose, _, _ = pose_at(cells, progress, hard_cut=hard_cut)
            pose = pose.resize((round(GRID_SIZE[0] * CHARACTER_SCALE), round(GRID_SIZE[1] * CHARACTER_SCALE)), Image.Resampling.LANCZOS)
            x = action_position(key, progress)
            y = GROUND_Y - pose.height
            frame.alpha_composite(shadow_layer(key, x, pose))
            if partner_cells and not record["solo"]:
                compose_partner(frame, partner_cells, key, progress)
            frame.alpha_composite(pose, (x - pose.width // 2, y))
            writer.append_data(np.asarray(frame.convert("RGB")))
    return {"path": str(output_path), "size": [WIDTH, HEIGHT], "fps": FPS, "frame_count": FRAME_COUNT, "duration_seconds": 8.0, "codec": "H.264/libx264", "hard_cut_policy": hard_cut, "partner_layer": bool(partner_cells and not record["solo"]), "scene_layer": key in TRAVEL_ACTIONS or key in {"protect", "warn", "rescue", "dodge", "block"}}


def build_overview(group: str, records: list[dict[str, Any]], output_dir: Path) -> None:
    entries = [record for record in records if record["group"] == group]
    tile_w, tile_h, label_h = 240, 135, 28
    columns = 4
    rows = math.ceil(len(entries) / columns)
    overview = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), "#f0f3f7")
    draw = ImageDraw.Draw(overview)
    for index, record in enumerate(entries):
        video = Path(record["hq_video_path"])
        reader = imageio.get_reader(str(video))
        image = Image.fromarray(reader.get_data(170)).convert("RGB")
        reader.close()
        image.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (tile_w, tile_h), "#111722")
        tile.paste(image, ((tile_w - image.width) // 2, (tile_h - image.height) // 2))
        row, column = divmod(index, columns)
        x, y = column * tile_w, row * (tile_h + label_h)
        overview.paste(tile, (x, y))
        draw.text((x + 5, y + tile_h + 6), record["key"], fill="#1c2734", font=font(14))
    target = output_dir / group
    target.mkdir(parents=True, exist_ok=True)
    overview.save(target / "group_overview.png", "PNG", optimize=True)


def main() -> None:
    args = parse_args()
    source_manifest = read_catalog()
    records = list(source_manifest["records"])
    if args.only:
        requested = set(args.only)
        records = [record for record in records if record["key"] in requested]
    if args.limit:
        records = records[: args.limit]
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    background_cache = {group: fit_background_source(path) for group, path in base.BACKGROUND_BY_GROUP.items() if path.is_file()}
    partner_path = partner_source()
    partner_cells = load_cells(partner_path) if partner_path else None
    output_records = []
    for index, record in enumerate(records, start=1):
        group_dir = OUTPUT_ROOT / record["group"]
        group_dir.mkdir(parents=True, exist_ok=True)
        output_path = group_dir / f"{base.CHARACTER}_{record['key']}_hq.mp4"
        if not (args.skip_existing and output_path.is_file()):
            info = render_record(record, background_cache, partner_cells, output_path)
        else:
            info = {
                "path": str(output_path),
                "size": [WIDTH, HEIGHT],
                "fps": FPS,
                "frame_count": FRAME_COUNT,
                "duration_seconds": 8.0,
                "codec": "H.264/libx264",
                "hard_cut_policy": record.get("asset_kind") == "generated_composite" or record["key"] not in HQ_BLENDS,
                "partner_layer": bool(partner_cells and not record["solo"]),
                "scene_layer": record["key"] in TRAVEL_ACTIONS or record["key"] in {"protect", "warn", "rescue", "dodge", "block"},
                "skipped_existing": True,
            }
        output_records.append({**record, "hq_video_path": str(output_path), "quality_render": info})
        print(f"[{index:03d}/{len(records):03d}] {record['key']} hard_cut={info.get('hard_cut_policy')} partner={info.get('partner_layer')}", flush=True)

    manifest = {
        "manifest_version": "round100-hq-v1",
        "status": "rendered",
        "source_catalog": str(CATALOG_PATH),
        "record_count": len(output_records),
        "quality_policy": {
            "full_body_alpha_dissolve": False,
            "low_overlap_pose_cut": True,
            "generated_composite_pose_cut": True,
            "partner_required_layers": True,
            "scene_layers": True,
        },
        "format": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": FRAME_COUNT, "duration_seconds": 8.0, "codec": "H.264/libx264"},
        "records": output_records,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for group in base.BACKGROUND_BY_GROUP:
        if any(record["group"] == group for record in output_records):
            build_overview(group, output_records, OUTPUT_ROOT)
    print(json.dumps({"record_count": len(output_records), "manifest": str(MANIFEST_PATH), "output_root": str(OUTPUT_ROOT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
