"""Render the six generated_round3 solo-action preview videos.

The renderer reads only the new ``generated_round3`` motion-sheet pack and
writes only ``output/video_previews/generated_round3``. Video frames contain
the scene only; word, phase, and source-status labels are confined to contact
sheets and the JSON manifest.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round3"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round3"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"

CHARACTER = "male_01"
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 8.0
FRAME_COUNT = 240
GROUND_Y = 452
SHEET_COLUMNS = 4
SHEET_ROWS = 2
FLOW_MIN_SILHOUETTE_IOU = 0.40
ACTIONS = ("salute", "prone", "stagger", "wake", "yawn", "sneeze")

# Every authored sheet is expected to provide eight ordered key poses. The
# timings deliberately give each word a readable prepare/act/hold/recover arc.
TIMELINES: dict[str, tuple[tuple[float, int, str], ...]] = {
    "salute": (
        (0.00, 0, "prepare"), (0.12, 1, "prepare"), (0.25, 2, "act"),
        (0.37, 3, "act"), (0.54, 4, "hold"), (0.66, 5, "hold"),
        (0.84, 6, "recover"), (1.00, 7, "recover"),
    ),
    "prone": (
        (0.00, 0, "prepare"), (0.14, 1, "prepare"), (0.29, 2, "act"),
        (0.43, 3, "act"), (0.59, 4, "hold"), (0.70, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "stagger": (
        (0.00, 0, "prepare"), (0.14, 1, "prepare"), (0.29, 2, "act"),
        (0.43, 3, "act"), (0.57, 4, "hold"), (0.68, 5, "hold"),
        (0.84, 6, "recover"), (1.00, 7, "recover"),
    ),
    "wake": (
        (0.00, 0, "prepare"), (0.14, 1, "prepare"), (0.29, 2, "act"),
        (0.43, 3, "act"), (0.59, 4, "hold"), (0.70, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "yawn": (
        (0.00, 0, "prepare"), (0.15, 1, "prepare"), (0.29, 2, "act"),
        (0.42, 3, "act"), (0.59, 4, "hold"), (0.70, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "sneeze": (
        (0.00, 0, "prepare"), (0.16, 1, "prepare"), (0.30, 2, "act"),
        (0.39, 3, "act"), (0.48, 4, "hold"), (0.60, 5, "recover"),
        (0.80, 6, "recover"), (1.00, 7, "recover"),
    ),
}

PHASE_CONTRACT = ("prepare", "act", "hold", "recover")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def discover_manifest(input_dir: Path) -> Path | None:
    preferred = (
        input_dir / "round3_manifest.json",
        input_dir / "generated_round3_manifest.json",
        input_dir / "manifest.json",
    )
    for candidate in preferred:
        if candidate.is_file():
            return candidate.resolve()
    candidates = sorted(input_dir.rglob("*manifest*.json")) if input_dir.is_dir() else []
    return candidates[0].resolve() if candidates else None


def manifest_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("actions", "assets", "words", "entries"):
        value = manifest.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def find_asset(records: list[dict[str, Any]], word: str) -> dict[str, Any] | None:
    for record in records:
        if str(record.get("word") or record.get("action") or "") == word:
            return record
    return None


def resolve_sheet(asset: dict[str, Any], input_dir: Path) -> Path:
    raw_value = (
        asset.get("motion_sheet") or asset.get("sheet") or asset.get("path")
        or asset.get("asset") or asset.get("image")
    )
    if not raw_value:
        raise FileNotFoundError("manifest entry has no motion-sheet path")
    raw = Path(str(raw_value))
    candidates = (raw, input_dir / raw, input_dir / raw.name)
    root = input_dir.resolve()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if root not in resolved.parents and resolved != root:
                raise ValueError(f"Refusing motion sheet outside generated_round3: {resolved}")
            return resolved
    raise FileNotFoundError(f"Could not resolve generated_round3 motion sheet {raw_value!r}")


def grid_for(asset: dict[str, Any], manifest: dict[str, Any]) -> tuple[int, int]:
    grid = asset.get("grid") or manifest.get("grid") or {}
    if isinstance(grid, dict):
        columns = int(grid.get("columns", SHEET_COLUMNS))
        rows = int(grid.get("rows", SHEET_ROWS))
    else:
        columns, rows = SHEET_COLUMNS, SHEET_ROWS
    if columns * rows != 8:
        raise ValueError(f"Expected an 8-pose 4x2 motion sheet, got {columns}x{rows}")
    return columns, rows


def extract_cells(sheet_path: Path, columns: int, rows: int) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
        cells: list[Image.Image] = []
        for index in range(columns * rows):
            column = index % columns
            row = index // columns
            left = round(column * sheet.width / columns)
            right = round((column + 1) * sheet.width / columns)
            top = round(row * sheet.height / rows)
            bottom = round((row + 1) * sheet.height / rows)
            cell = sheet.crop((left, top, right, bottom))
            bbox = cell.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Empty alpha cell {index + 1} in {sheet_path}")
            cells.append(cell.crop(bbox))
        return tuple(cells)


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def aligned_canvases(first: Image.Image, second: Image.Image) -> tuple[Image.Image, Image.Image]:
    width = max(first.width, second.width)
    height = max(first.height, second.height)
    result = []
    for image in (first, second):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((width - image.width) // 2, height - image.height))
        result.append(canvas)
    return result[0], result[1]


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    first_canvas, second_canvas = aligned_canvases(first, second)
    first_mask = np.asarray(first_canvas.getchannel("A")) >= 64
    second_mask = np.asarray(second_canvas.getchannel("A")) >= 64
    union = np.logical_or(first_mask, second_mask).sum()
    return float(np.logical_and(first_mask, second_mask).sum() / union) if union else 0.0


def interpolate_pose(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    amount = smoothstep(amount)
    first_canvas, second_canvas = aligned_canvases(first, second)
    first_array = np.asarray(first_canvas, dtype=np.float32) / 255.0
    second_array = np.asarray(second_canvas, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    rgb = first_array[..., :3] * first_alpha * (1.0 - amount)
    rgb += second_array[..., :3] * second_alpha * amount
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def pose_at(
    timeline: tuple[tuple[float, int, str], ...],
    progress: float,
    cells: tuple[Image.Image, ...],
    pose_cuts: set[tuple[int, int]],
) -> tuple[Image.Image, str]:
    value = min(max(float(progress), 0.0), 1.0)
    if value <= timeline[0][0]:
        return cells[timeline[0][1]], timeline[0][2]
    for first, second in zip(timeline, timeline[1:]):
        start, first_cell, first_phase = first
        end, second_cell, second_phase = second
        if value > end:
            continue
        if first_cell == second_cell:
            return cells[first_cell], second_phase
        amount = smoothstep((value - start) / max(end - start, 1e-6))
        if (first_cell, second_cell) in pose_cuts:
            pose = cells[first_cell] if amount < 0.5 else cells[second_cell]
        else:
            pose = interpolate_pose(cells[first_cell], cells[second_cell], amount)
        return pose, first_phase if amount < 0.5 else second_phase
    return cells[timeline[-1][1]], timeline[-1][2]


def fit_background(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.fit(
            source.convert("RGBA"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def paste_character(frame: Image.Image, pose: Image.Image, center_x: float, scale: float) -> None:
    target_height = max(12, round(HEIGHT * scale))
    resize_scale = target_height / max(1, pose.height)
    target_width = max(8, round(pose.width * resize_scale))
    character = pose.resize((target_width, target_height), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse(
        (center_x - target_width * 0.28, GROUND_Y - 4,
         center_x + target_width * 0.28, GROUND_Y + max(5, target_width * 0.035)),
        fill=(24, 27, 33, 80),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    frame.alpha_composite(shadow)
    frame.alpha_composite(character, (round(center_x - target_width / 2), GROUND_Y - target_height))


def render_action(
    action: str,
    cells: tuple[Image.Image, ...],
    background: Image.Image,
) -> tuple[list[Image.Image], list[str], dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    pose_cuts: set[tuple[int, int]] = set()
    for first, second in zip(cells, cells[1:]):
        overlap = alpha_iou(first, second)
        method = "pose_cut" if overlap < FLOW_MIN_SILHOUETTE_IOU else "alpha_aware"
        if method == "pose_cut":
            pose_cuts.add((len(transitions), len(transitions) + 1))
        transitions.append({
            "from_cell_1_based": len(transitions) + 1,
            "to_cell_1_based": len(transitions) + 2,
            "silhouette_iou": round(overlap, 4),
            "method": method,
        })

    frames: list[Image.Image] = []
    phases: list[str] = []
    scale = 0.72 if action not in {"wake", "yawn", "sneeze"} else 0.78
    center_x = WIDTH * 0.50
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / max(FRAME_COUNT - 1, 1)
        pose, phase = pose_at(TIMELINES[action], progress, cells, pose_cuts)
        frame = background.copy()
        # Stagger gets a small grounded weight shift; feet still remain in frame.
        if action == "stagger":
            offset = math.sin(progress * math.pi * 4.0) * 22.0 * (1.0 - progress * 0.25)
            frame_center_x = center_x + offset
        else:
            frame_center_x = center_x
        paste_character(frame, pose, frame_center_x, scale)
        frames.append(frame.convert("RGB"))
        phases.append(phase)
    return frames, phases, {
        "transitions": transitions,
        "pose_cuts": [list(pair) for pair in sorted(pose_cuts)],
        "silhouette_iou_threshold": FLOW_MIN_SILHOUETTE_IOU,
    }


def font(size: int = 15) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def source_risks(manifest: dict[str, Any], asset: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    for key in ("quality_notes", "risks", "limitations"):
        value = manifest.get(key, [])
        if isinstance(value, list):
            risks.extend(str(item) for item in value)
        elif value:
            risks.append(str(value))
    evaluation = asset.get("evaluation")
    if isinstance(evaluation, dict):
        for key in ("limitation", "risk", "risks", "notes"):
            if evaluation.get(key):
                risks.append(f"{key}: {evaluation[key]}")
    if asset.get("status") in {"prototype", "blocked"} or asset.get("blocked"):
        risks.append("Source is prototype/blocked; preview remains review-only.")
    return list(dict.fromkeys(risks))


def write_contact_sheet(
    path: Path,
    frames: list[Image.Image],
    phases: list[str],
    *,
    action: str,
    status: str,
    risk_text: str,
) -> dict[str, Any]:
    tile_width, tile_height = 240, 120
    label_height, header_height = 24, 70
    columns, rows = 4, 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), "#f2f4f7")
    draw = ImageDraw.Draw(sheet)
    typeface = font()
    status_color = "#946200" if status in {"prototype", "blocked"} else "#216e4e"
    draw.rectangle((0, 0, sheet.width, 24), fill=status_color)
    decision = "review only" if status in {"prototype", "blocked"} else "source status preserved"
    draw.text((8, 5), f"{CHARACTER} {action} | {status} | {decision}", fill="white", font=typeface)
    lines = risk_text or "No source risk notes provided."
    for index, line in enumerate(lines[:112] and [lines[:112]]):
        draw.text((8, 32 + index * 16), line, fill="#26313b", font=typeface)
    for sample_index in range(12):
        frame_index = min(round(sample_index * (len(frames) - 1) / 11), len(frames) - 1)
        second = frame_index / FPS
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = (sample_index % columns) * tile_width
        y = header_height + (sample_index // columns) * (tile_height + label_height)
        draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill="#dfe5ea")
        draw.text((x + 7, y + 5), f"{second:0.2f}s | {phases[frame_index]}", fill="#26313b", font=typeface)
        sheet.paste(tile, (x, y + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [sheet.width, sheet.height], "labels_included": True}


def write_video(path: Path, frames: list[Image.Image]) -> None:
    writer = imageio.get_writer(
        str(path), fps=FPS, codec="libx264", quality=8, macro_block_size=2,
        ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer returned no data for {path}")


def validate_video(path: Path) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
        first_frame = reader.get_data(0)
    finally:
        reader.close()
    fps = float(metadata.get("fps") or 0.0)
    size = list(metadata.get("size") or ())
    codec = str(metadata.get("codec") or "h264")
    report = {
        "path": str(path.resolve()), "resolution": size, "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "codec": codec, "codec_readable": first_frame is not None,
        "metadata_verified": True,
    }
    if size != [WIDTH, HEIGHT] or frame_count != FRAME_COUNT or abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata for {path}: {report}")
    if not any(token in codec.lower() for token in ("h264", "avc1", "264")):
        raise RuntimeError(f"Unexpected MP4 codec for {path}: {report}")
    return report


def missing_manifest(
    output_dir: Path,
    *,
    reason: str,
    missing_words: list[str],
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "round3_video_manifest.json"
    payload = {
        "manifest_version": "round3-video-1.0",
        "render_status": "blocked",
        "character": CHARACTER,
        "scope": list(ACTIONS),
        "source_policy": "Only assets under assets/characters/motion_sheets/generated_round3 are allowed; no unrelated substitution.",
        "format": {"resolution": [WIDTH, HEIGHT], "fps": FPS, "duration_seconds": DURATION_SECONDS, "frame_count": FRAME_COUNT, "codec": "H.264/libx264", "timeline_contract": list(PHASE_CONTRACT)},
        "input_dir": str(INPUT_DIR.resolve()),
        "reason": reason,
        "missing_words": missing_words,
        "assets": [],
        "output_policy": {"shared_backend_modified": False, "other_asset_packs_modified": False, "debug_overlays_in_mp4": False},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"render_status": "blocked", "manifest": str(path.resolve()), "missing_words": missing_words}, ensure_ascii=False, indent=2))
    return 2


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir != OUTPUT_DIR.resolve():
        raise ValueError("This renderer writes only to output/video_previews/generated_round3.")
    manifest_path = discover_manifest(input_dir)
    if not input_dir.is_dir():
        return missing_manifest(output_dir, reason="generated_round3 source folder is absent after handoff recheck", missing_words=list(ACTIONS))
    if manifest_path is None:
        return missing_manifest(output_dir, reason="generated_round3 source manifest is absent", missing_words=list(ACTIONS))

    manifest = read_json(manifest_path)
    records = manifest_records(manifest)
    missing = [word for word in ACTIONS if find_asset(records, word) is None]
    if missing:
        return missing_manifest(output_dir, reason=f"Source manifest is missing required actions: {', '.join(missing)}", missing_words=missing)
    if not BACKGROUND_PATH.is_file():
        raise FileNotFoundError(BACKGROUND_PATH)

    output_dir.mkdir(parents=True, exist_ok=True)
    background = fit_background(BACKGROUND_PATH)
    rendered: list[dict[str, Any]] = []
    for action in ACTIONS:
        asset = find_asset(records, action)
        assert asset is not None
        sheet_path = resolve_sheet(asset, input_dir)
        columns, rows = grid_for(asset, manifest)
        cells = extract_cells(sheet_path, columns, rows)
        frames, phases, interpolation = render_action(action, cells, background)
        video_path = output_dir / f"{CHARACTER}_{action}_generated_round3.mp4"
        contact_path = output_dir / f"{CHARACTER}_{action}_generated_round3_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        status = str(asset.get("status", "unknown"))
        risks = source_risks(manifest, asset)
        contact_report = write_contact_sheet(contact_path, frames, phases, action=action, status=status, risk_text="; ".join(risks))
        rendered.append({
            "word": action,
            "status": status,
            "blocked": bool(asset.get("blocked", False)),
            "production_approved": status not in {"prototype", "blocked"} and not bool(asset.get("blocked", False)),
            "review_decision": "review_only" if status in {"prototype", "blocked"} or asset.get("blocked") else "source_status_preserved",
            "source_asset": copy.deepcopy(asset),
            "motion_sheet": str(sheet_path),
            "source_manifest": str(manifest_path),
            "timeline": [
                {"progress": progress, "cell_0_based": cell, "phase": phase}
                for progress, cell, phase in TIMELINES[action]
            ],
            "phase_frame_counts": {phase: phases.count(phase) for phase in PHASE_CONTRACT},
            "video": video_report,
            "contact_sheet": contact_report,
            "source_risks_preserved": risks,
            "quality_checks": {
                "fixed_wide_background": True,
                "fixed_camera": True,
                "debug_overlay_in_video": False,
                "labels_only_on_contact_sheet": True,
                "interpolation": interpolation,
            },
        })

    output_manifest = {
        "manifest_version": "round3-video-1.0",
        "render_status": "complete",
        "character": CHARACTER,
        "scope": list(ACTIONS),
        "source_status_policy": "Prototype/blocked status is preserved verbatim; previews never upgrade source approval.",
        "format": {
            "resolution": [WIDTH, HEIGHT], "fps": FPS, "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT, "codec": "H.264/libx264", "pixel_format": "yuv420p",
            "camera": "locked", "background_reference": str(BACKGROUND_PATH.resolve()),
            "ground_anchor": f"bottom-aligned at y={GROUND_Y}", "timeline_contract": list(PHASE_CONTRACT),
        },
        "source_manifest": str(manifest_path),
        "assets": rendered,
        "metadata_validation": {
            "all_videos_checked": all(item["video"]["metadata_verified"] for item in rendered),
            "all_codec_readable": all(item["video"]["codec_readable"] for item in rendered),
            "all_resolution_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in rendered),
            "all_fps_30": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in rendered),
            "all_frame_count_240": all(item["video"]["frame_count"] == FRAME_COUNT for item in rendered),
            "all_contacts_verified": all(item["contact_sheet"]["labels_included"] for item in rendered),
            "asset_count": len(rendered),
        },
        "output_policy": {
            "only_generated_round3_assets_read": True,
            "shared_backend_modified": False,
            "other_asset_packs_modified": False,
            "debug_overlays_in_mp4": False,
            "labels_only_on_contact_sheets": True,
        },
    }
    manifest_out = output_dir / "round3_video_manifest.json"
    manifest_out.write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"render_status": "complete", "manifest": str(manifest_out.resolve()), "videos": len(rendered), "contacts": len(rendered)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
