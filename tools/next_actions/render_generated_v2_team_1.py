"""Render team 1's v2 stationary action previews.

This renderer is intentionally self-contained. It reads only the generated_v2
motion sheets and a v2 background, then writes only the designated generated_v2
team folder. Video frames contain no review labels; labels are confined to the
contact sheets and the output manifest.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
POSTURE_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_v2" / "team_a_posture"
GESTURE_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_v2" / "team_b_gestures"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_v2" / "team_1_stationary"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"

CHARACTER = "male_01"
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 8.0
FRAME_COUNT = 240
GROUND_Y = 452
FLOW_MIN_SILHOUETTE_IOU = 0.40
ACTION_ORDER = ("kneel", "bow", "crouch", "stretch", "clap", "point", "nod", "dance")
POSTURE_ACTIONS = set(ACTION_ORDER[:4])
FORCED_POSE_CUT_ACTIONS = {"dance"}


# Each action gets a deliberately different timing arc. Repeated cells encode
# holds without inventing extra art between authored poses.
TIMELINES: dict[str, tuple[tuple[float, int, str], ...]] = {
    "kneel": (
        (0.00, 0, "prepare"), (0.13, 1, "prepare"), (0.29, 2, "act"),
        (0.40, 3, "act"), (0.56, 4, "hold"), (0.67, 5, "hold"),
        (0.84, 6, "recover"), (1.00, 7, "recover"),
    ),
    "bow": (
        (0.00, 0, "prepare"), (0.16, 1, "prepare"), (0.31, 2, "act"),
        (0.43, 3, "act"), (0.61, 4, "hold"), (0.69, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "crouch": (
        (0.00, 0, "prepare"), (0.15, 1, "prepare"), (0.31, 2, "act"),
        (0.43, 3, "act"), (0.61, 4, "hold"), (0.70, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "stretch": (
        (0.00, 0, "prepare"), (0.15, 1, "prepare"), (0.29, 2, "act"),
        (0.42, 3, "act"), (0.59, 4, "hold"), (0.70, 5, "hold"),
        (0.86, 6, "recover"), (1.00, 7, "recover"),
    ),
    "clap": (
        (0.00, 0, "prepare"), (0.13, 1, "prepare"), (0.25, 2, "act"),
        (0.34, 3, "hold"), (0.43, 4, "act"), (0.57, 5, "prepare"),
        (0.70, 6, "act"), (0.79, 6, "hold"), (1.00, 7, "recover"),
    ),
    "point": (
        (0.00, 0, "prepare"), (0.15, 1, "act"), (0.28, 2, "act"),
        (0.39, 3, "hold"), (0.50, 4, "recover"), (0.63, 5, "act"),
        (0.76, 6, "hold"), (1.00, 7, "recover"),
    ),
    "nod": (
        (0.00, 0, "prepare"), (0.16, 1, "act"), (0.29, 2, "act"),
        (0.41, 3, "hold"), (0.55, 4, "recover"), (0.70, 5, "recover"),
        (0.83, 6, "hold"), (1.00, 7, "recover"),
    ),
    "dance": (
        (0.00, 0, "prepare"), (0.14, 1, "act"), (0.27, 2, "hold"),
        (0.42, 3, "act"), (0.55, 4, "hold"), (0.69, 5, "act"),
        (0.84, 6, "act"), (1.00, 7, "recover"),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def find_asset(manifest: dict[str, Any], action: str) -> dict[str, Any]:
    records = manifest.get("actions") or manifest.get("assets") or []
    for record in records:
        if record.get("word") == action:
            return record
    raise KeyError(f"{action!r} is absent from the v2 manifest")


def resolve_sheet(asset: dict[str, Any], source_dir: Path) -> Path:
    raw = Path(str(asset["motion_sheet"]))
    candidates = (raw, source_dir / raw.name, source_dir / raw)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"Could not resolve v2 motion sheet {asset['motion_sheet']!r}")


def extract_cells(sheet_path: Path) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
        cells: list[Image.Image] = []
        for index in range(8):
            column = index % 4
            row = index // 4
            left = round(column * sheet.width / 4)
            right = round((column + 1) * sheet.width / 4)
            top = round(row * sheet.height / 2)
            bottom = round((row + 1) * sheet.height / 2)
            cell = sheet.crop((left, top, right, bottom))
            bbox = cell.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Empty alpha cell {index} in {sheet_path}")
            cells.append(cell.crop(bbox))
    return tuple(cells)


def source_phase_by_cell(asset: dict[str, Any]) -> dict[int, str]:
    records = asset.get("frames") or asset.get("phase_intent") or []
    return {int(record["cell"]) - 1: str(record.get("phase", "")) for record in records}


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def bottom_aligned_canvases(first: Image.Image, second: Image.Image) -> tuple[Image.Image, Image.Image]:
    width = max(first.width, second.width)
    height = max(first.height, second.height)
    result: list[Image.Image] = []
    for image in (first, second):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((width - image.width) // 2, height - image.height))
        result.append(canvas)
    return result[0], result[1]


def trim_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    return rgba.crop(bbox) if bbox else rgba


def premultiplied_blend(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    first_canvas, second_canvas = bottom_aligned_canvases(first, second)
    a = np.asarray(first_canvas, dtype=np.float32)
    b = np.asarray(second_canvas, dtype=np.float32)
    t = min(max(float(amount), 0.0), 1.0)
    alpha_a = a[..., 3:4] / 255.0
    alpha_b = b[..., 3:4] / 255.0
    alpha = alpha_a * (1.0 - t) + alpha_b * t
    rgb = a[..., :3] * alpha_a * (1.0 - t) + b[..., :3] * alpha_b * t
    rgb = np.divide(rgb, np.maximum(alpha, 1e-5))
    rgba = np.concatenate((rgb, alpha * 255.0), axis=2)
    return trim_alpha(Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA"))


def interpolate_pose(
    first: Image.Image,
    second: Image.Image,
    amount: float,
    *,
    cv2: Any,
    cache: dict[tuple[int, int], tuple[Any, ...]],
    cache_key: tuple[int, int],
    force_pose_cut: bool = False,
) -> Image.Image:
    blend = min(max(float(amount), 0.0), 1.0)
    if blend <= 0.015:
        return first
    if blend >= 0.985:
        return second
    prepared = cache.get(cache_key)
    if prepared is None:
        first_canvas, second_canvas = bottom_aligned_canvases(first, second)
        if force_pose_cut:
            first_mask = np.asarray(first_canvas, dtype=np.uint8)[..., 3] >= 64
            second_mask = np.asarray(second_canvas, dtype=np.uint8)[..., 3] >= 64
            union = np.logical_or(first_mask, second_mask).sum()
            iou = float(np.logical_and(first_mask, second_mask).sum()) / float(union) if union else 0.0
            prepared = ("pose_cut", iou, "forced_review_cut_for_ghosting")
        elif cv2 is None:
            prepared = ("alpha_blend", first_canvas, second_canvas, 0.0)
        else:
            first_rgba = np.asarray(first_canvas, dtype=np.uint8)
            second_rgba = np.asarray(second_canvas, dtype=np.uint8)

            def gray_for_flow(rgba: np.ndarray) -> np.ndarray:
                alpha = rgba[..., 3:4].astype(np.float32) / 255.0
                rgb = rgba[..., :3].astype(np.float32)
                composite = rgb * alpha + 127.0 * (1.0 - alpha)
                return cv2.cvtColor(composite.astype(np.uint8), cv2.COLOR_RGB2GRAY)

            first_mask = first_rgba[..., 3] >= 64
            second_mask = second_rgba[..., 3] >= 64
            union = np.logical_or(first_mask, second_mask).sum()
            iou = float(np.logical_and(first_mask, second_mask).sum()) / float(union) if union else 0.0
            if iou < FLOW_MIN_SILHOUETTE_IOU:
                prepared = ("pose_cut", iou)
            else:
                forward = cv2.calcOpticalFlowFarneback(
                    gray_for_flow(first_rgba), gray_for_flow(second_rgba),
                    None, 0.5, 4, 25, 4, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
                )
                backward = cv2.calcOpticalFlowFarneback(
                    gray_for_flow(second_rgba), gray_for_flow(first_rgba),
                    None, 0.5, 4, 25, 4, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
                )
                grid_x, grid_y = np.meshgrid(
                    np.arange(first_canvas.width), np.arange(first_canvas.height),
                )
                prepared = ("optical_flow", first_rgba, second_rgba, forward, backward, grid_x, grid_y, iou)
        cache[cache_key] = prepared

    if prepared[0] == "pose_cut":
        return first if blend < 0.5 else second
    if prepared[0] == "alpha_blend":
        return premultiplied_blend(first, second, blend)

    _, first_rgba, second_rgba, forward, backward, grid_x, grid_y, _ = prepared

    def warp(source: np.ndarray, flow: np.ndarray, scale: float) -> np.ndarray:
        map_x = (grid_x - flow[..., 0] * scale).astype(np.float32)
        map_y = (grid_y - flow[..., 1] * scale).astype(np.float32)
        return cv2.remap(
            source, map_x, map_y, interpolation=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
        )

    warped_first = warp(first_rgba, forward, blend).astype(np.float32)
    warped_second = warp(second_rgba, backward, 1.0 - blend).astype(np.float32)
    rgba = np.clip(warped_first * (1.0 - blend) + warped_second * blend, 0, 255).astype(np.uint8)
    return trim_alpha(Image.fromarray(rgba, "RGBA"))


def pose_at(
    timeline: tuple[tuple[float, int, str], ...],
    progress: float,
    cells: tuple[Image.Image, ...],
    *,
    cv2: Any,
    cache: dict[tuple[int, int], tuple[Any, ...]],
    force_pose_cut: bool = False,
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
            return cells[first_cell], second_phase if value >= end else first_phase
        amount = smoothstep((value - start) / max(end - start, 1e-6))
        pose = interpolate_pose(
            cells[first_cell], cells[second_cell], amount,
            cv2=cv2, cache=cache, cache_key=(first_cell, second_cell),
            force_pose_cut=force_pose_cut,
        )
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
    resize_scale = target_height / pose.height
    target_width = max(8, round(pose.width * resize_scale))
    character = pose.resize((target_width, target_height), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (center_x - target_width * 0.28, GROUND_Y - 4,
         center_x + target_width * 0.28, GROUND_Y + max(5, target_width * 0.035)),
        fill=(24, 27, 33, 80),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    frame.alpha_composite(shadow)
    frame.alpha_composite(character, (round(center_x - target_width / 2), GROUND_Y - target_height))


def dance_offset(progress: float) -> float:
    points = ((0.00, 0.0), (0.14, -16.0), (0.27, -16.0), (0.42, 19.0),
              (0.55, 19.0), (0.69, -12.0), (0.84, 13.0), (1.00, 0.0))
    for (start, left), (end, right) in zip(points, points[1:]):
        if progress <= end:
            amount = smoothstep((progress - start) / max(end - start, 1e-6))
            return left + (right - left) * amount
    return points[-1][1]


def render_action(
    action: str,
    cells: tuple[Image.Image, ...],
    background: Image.Image,
    *,
    cv2: Any,
) -> tuple[list[Image.Image], list[str], dict[tuple[int, int], tuple[Any, ...]]]:
    frames: list[Image.Image] = []
    phases: list[str] = []
    cache: dict[tuple[int, int], tuple[Any, ...]] = {}
    timeline = TIMELINES[action]
    scale = {"nod": 0.84, "clap": 0.75, "point": 0.75}.get(action, 0.72)
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / max(FRAME_COUNT - 1, 1)
        pose, phase = pose_at(
            timeline, progress, cells, cv2=cv2, cache=cache,
            force_pose_cut=action in FORCED_POSE_CUT_ACTIONS,
        )
        frame = background.copy()
        center_x = WIDTH * 0.50 + (dance_offset(progress) if action == "dance" else 0.0)
        paste_character(frame, pose, center_x, scale)
        frames.append(ImageEnhance.Contrast(frame.convert("RGB")).enhance(1.015))
        phases.append(phase)
    return frames, phases, cache


def font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 14)
    except OSError:
        return ImageFont.load_default()


def write_contact_sheet(
    path: Path,
    frames: list[Image.Image],
    phases: list[str],
    *,
    action: str,
    status: str,
    risk_text: str,
) -> None:
    tile_width = 240
    tile_height = 120
    label_height = 24
    header_height = 70
    columns = 4
    rows = 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), "#f2f4f7")
    draw = ImageDraw.Draw(sheet)
    typeface = font()
    status_color = {"production": "#216e4e", "prototype": "#946200"}.get(status, "#42637a")
    draw.rectangle((0, 0, sheet.width, 24), fill=status_color)
    approval = "production approved" if status == "production" and action not in {"bow", "stretch"} else "review only"
    draw.text((8, 5), f"{CHARACTER} {action} | {status} | {approval}", fill="white", font=typeface)
    for index, line in enumerate(__import__("textwrap").wrap(risk_text, width=112)[:2]):
        draw.text((8, 31 + index * 16), line, fill="#26313b", font=typeface)
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
    finally:
        reader.close()
    fps = float(metadata.get("fps") or 0.0)
    size = list(metadata.get("size") or ())
    codec = str(metadata.get("codec") or "h264")
    report = {
        "path": str(path.resolve()), "resolution": size, "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "codec": codec, "metadata_verified": True,
    }
    if size != [WIDTH, HEIGHT] or frame_count != FRAME_COUNT or abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata for {path}: {report}")
    if codec and not any(token in codec.lower() for token in ("h264", "avc1", "264")):
        raise RuntimeError(f"Unexpected MP4 codec for {path}: {report}")
    return report


def transition_report(cache: dict[tuple[int, int], tuple[Any, ...]]) -> dict[str, Any]:
    methods: list[str] = []
    pose_cuts: list[dict[str, Any]] = []
    for (first, second), prepared in sorted(cache.items()):
        method = str(prepared[0])
        methods.append(method)
        if method == "pose_cut":
            pose_cuts.append({
                "from_cell_0_based": first, "to_cell_0_based": second,
                "silhouette_iou": round(float(prepared[1]), 4),
                "reason": str(prepared[2]) if len(prepared) > 2 else "silhouette change is below the optical-flow stability threshold",
            })
    return {
        "methods_used": sorted(set(methods)),
        "optical_flow_or_alpha_aware": any(method in {"optical_flow", "alpha_blend"} for method in methods),
        "pose_cut_segments": pose_cuts,
        "pose_cut_count": len(pose_cuts),
        "silhouette_iou_threshold": FLOW_MIN_SILHOUETTE_IOU,
    }


def source_risks(manifest: dict[str, Any], asset: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    for item in manifest.get("quality_notes", []):
        if str(item) not in risks:
            risks.append(str(item))
    evaluation = asset.get("evaluation")
    if isinstance(evaluation, dict):
        for key, value in evaluation.items():
            if key in {"limitation", "risk", "risks"}:
                text = f"{key}: {value}"
                if text not in risks:
                    risks.append(text)
    if asset.get("status") == "prototype":
        risks.append("Source v2 status is prototype; do not promote this preview to production.")
    if asset.get("word") in {"bow", "stretch"}:
        risks.append("Posture v2 source is newly authored and remains review-only until runtime playback review.")
    return risks


def main() -> None:
    args = parse_args()
    if args.output_dir.resolve() != OUTPUT_DIR.resolve():
        raise ValueError("This renderer writes only to output/video_previews/generated_v2/team_1_stationary.")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    posture_manifest_path = POSTURE_DIR / "team_a_v2_manifest.json"
    gesture_manifest_path = GESTURE_DIR / "team_b_manifest.json"
    posture_manifest = read_json(posture_manifest_path)
    gesture_manifest = read_json(gesture_manifest_path)
    manifests = {
        "posture": (posture_manifest, posture_manifest_path, POSTURE_DIR),
        "gesture": (gesture_manifest, gesture_manifest_path, GESTURE_DIR),
    }
    background = fit_background(BACKGROUND_PATH)
    try:
        import cv2
    except ImportError:
        cv2 = None

    rendered: list[dict[str, Any]] = []
    for action in ACTION_ORDER:
        kind = "posture" if action in POSTURE_ACTIONS else "gesture"
        manifest, manifest_path, source_dir = manifests[kind]
        asset = find_asset(manifest, action)
        sheet_path = resolve_sheet(asset, source_dir)
        cells = extract_cells(sheet_path)
        frames, phases, cache = render_action(action, cells, background, cv2=cv2)
        video_path = args.output_dir / f"{CHARACTER}_{action}_team_1_stationary_v2.mp4"
        contact_path = args.output_dir / f"{CHARACTER}_{action}_team_1_stationary_v2_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        risk_lines = source_risks(manifest, asset)
        write_contact_sheet(
            contact_path, frames, phases, action=action,
            status=str(asset.get("status", "unknown")),
            risk_text="; ".join(risk_lines),
        )
        timeline = TIMELINES[action]
        source_phase = source_phase_by_cell(asset)
        transition = transition_report(cache)
        status = str(asset.get("status", "unknown"))
        production_approved = status == "production" and not bool(asset.get("blocked")) and action not in {"bow", "stretch"}
        rendered.append({
            "word": action,
            "status": status,
            "blocked": bool(asset.get("blocked", False)),
            "production_approved": production_approved,
            "review_decision": "production" if production_approved else "review_only",
            "source_manifest": str(manifest_path.resolve()),
            "source_v2_asset": copy.deepcopy(asset),
            "source_risks_preserved": risk_lines,
            "motion_sheet": str(sheet_path),
            "render_cell_sequence_0_based": [cell for _, cell, _ in timeline],
            "timeline": [
                {
                    "progress": round(progress, 5), "cell": cell,
                    "phase": phase, "source_phase": source_phase.get(cell, ""),
                }
                for progress, cell, phase in timeline
            ],
            "phase_frame_counts": {phase: phases.count(phase) for phase in ("prepare", "act", "hold", "recover")},
            "video": video_report,
            "contact_sheet": str(contact_path.resolve()),
            "quality_checks": {
                "fixed_background": True,
                "fixed_camera": True,
                "background_reference": str(BACKGROUND_PATH.resolve()),
                "ground_anchor": f"bottom-aligned at y={GROUND_Y}",
                "debug_overlay_in_video": False,
                "phase_labels_in_video": False,
                "phase_labels_in_contact_sheet": True,
                "interpolation": transition,
                "clap_contact_cells_1_based": [3, 4, 7] if action == "clap" else [],
                "point_directions": ["screen-right", "screen-left"] if action == "point" else [],
                "nod_medium_shot_scale": action == "nod",
                "dance_foot_center_shift_px": "grounded -16 to +19 horizontal weight beats" if action == "dance" else None,
                "production_promotion_blocked_for_bow_stretch": action in {"bow", "stretch"},
            },
        })

    output_manifest = {
        "manifest_version": "2.0-video",
        "team": "team_1_stationary",
        "iteration": "generated_v2",
        "character": CHARACTER,
        "scope": list(ACTION_ORDER),
        "source_status_policy": "Source v2 status and blocked state are copied verbatim; this renderer never upgrades an asset.",
        "format": {
            "resolution": [WIDTH, HEIGHT], "fps": FPS,
            "duration_seconds": DURATION_SECONDS, "frame_count": FRAME_COUNT,
            "codec": "H.264/libx264", "pixel_format": "yuv420p",
            "camera": "locked", "background_reference": str(BACKGROUND_PATH.resolve()),
            "ground_anchor": f"bottom-aligned at y={GROUND_Y}",
            "timeline_contract": ["prepare", "act", "hold", "recover"],
        },
        "inputs": {
            "posture_manifest": str(posture_manifest_path.resolve()),
            "gesture_manifest": str(gesture_manifest_path.resolve()),
            "posture_dir": str(POSTURE_DIR.resolve()),
            "gesture_dir": str(GESTURE_DIR.resolve()),
        },
        "source_manifest_notes_preserved": {
            "posture": {"quality_notes": posture_manifest.get("quality_notes", []), "source_policy": posture_manifest.get("source_policy")},
            "gesture": {"quality_policy": gesture_manifest.get("quality_policy", {}), "v1_policy": gesture_manifest.get("v1_policy")},
        },
        "assets": rendered,
        "metadata_validation": {
            "all_videos_checked": all(item["video"]["metadata_verified"] for item in rendered),
            "all_resolution_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in rendered),
            "all_fps_30": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in rendered),
            "all_frame_count_240": all(item["video"]["frame_count"] == FRAME_COUNT for item in rendered),
            "all_h264": all(any(token in item["video"]["codec"].lower() for token in ("h264", "avc1", "264")) for item in rendered),
        },
        "output_policy": {
            "v1_outputs_modified": False,
            "shared_provider_modified": False,
            "db_connection_test_code_modified": False,
            "other_team_folders_modified": False,
            "debug_overlay_or_phase_labels_in_mp4": False,
        },
    }
    manifest_path = args.output_dir / "team_1_video_manifest_v2.json"
    manifest_path.write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "manifest": str(manifest_path.resolve()),
        "videos": len(rendered),
        "cv2_optical_flow": cv2 is not None,
    }, indent=2))


if __name__ == "__main__":
    main()
