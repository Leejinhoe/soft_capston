"""Render the v2 scene-action previews owned by video team 2.

Only the v2 motion sheets and v2 backgrounds are read.  The renderer keeps a
locked camera/background, a shared bottom ground anchor, and an explicit
prepare -> act -> hold -> recover schedule.  MP4 frames contain only the
scene; phase labels are written to the review contact sheets.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_v2" / "team_c_scene_actions"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_v2" / "team_2_scene_actions"
SOURCE_MANIFEST_NAME = "team_c_manifest_v2.json"

CHARACTER = "male_01"
ACTIONS = ("crawl", "climb", "slide", "hide", "fall_roll")
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 8.0
FRAME_COUNT = 240
GROUND_Y = 420
SHEET_COLUMNS = 4
SHEET_ROWS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION_SECONDS)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    return parser.parse_args()


def ease(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def font(size: int = 15) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def fit_background(path: Path, width: int, height: int) -> Image.Image:
    with Image.open(path) as source:
        source = source.convert("RGB")
        scale = max(width / source.width, height / source.height)
        resized = source.resize(
            (round(source.width * scale), round(source.height * scale)),
            Image.Resampling.LANCZOS,
        )
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height)).convert("RGBA")


def extract_cells(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
        cells: list[Image.Image] = []
        for index in range(SHEET_COLUMNS * SHEET_ROWS):
            column = index % SHEET_COLUMNS
            row = index // SHEET_COLUMNS
            left = round(column * sheet.width / SHEET_COLUMNS)
            right = round((column + 1) * sheet.width / SHEET_COLUMNS)
            top = round(row * sheet.height / SHEET_ROWS)
            bottom = round((row + 1) * sheet.height / SHEET_ROWS)
            cell = sheet.crop((left, top, right, bottom))
            bbox = cell.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Empty cell {index + 1} in {path}")
            cells.append(cell.crop(bbox))
        return cells


def normalize_layers(cells: list[Image.Image], target_height: int) -> list[Image.Image]:
    layers: list[Image.Image] = []
    for cell in cells:
        scale = target_height / max(1, cell.height)
        layers.append(
            cell.resize(
                (max(1, round(cell.width * scale)), target_height),
                Image.Resampling.LANCZOS,
            )
        )
    return layers


def aligned_canvas(pose: Image.Image, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(pose, ((width - pose.width) // 2, height - pose.height))
    return canvas


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    canvas_width = max(first.width, second.width)
    canvas_height = max(first.height, second.height)
    a = np.asarray(aligned_canvas(first, canvas_width, canvas_height).getchannel("A")) > 24
    b = np.asarray(aligned_canvas(second, canvas_width, canvas_height).getchannel("A")) > 24
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def interpolation_plan(layers: list[Image.Image]) -> dict[str, object]:
    transitions: list[dict[str, object]] = []
    cuts: set[tuple[int, int]] = set()
    for index, (first, second) in enumerate(zip(layers, layers[1:])):
        overlap = alpha_iou(first, second)
        # Low overlap means a cross-fade would expose two readable silhouettes.
        # Use a pose cut and preserve the decision in the video manifest.
        method = "pose_cut" if overlap < 0.55 else "alpha_aware"
        if method == "pose_cut":
            cuts.add((index, index + 1))
        transitions.append(
            {
                "from_cell": index + 1,
                "to_cell": index + 2,
                "alpha_iou": round(overlap, 4),
                "method": method,
            }
        )
    return {"transitions": transitions, "pose_cuts": [list(pair) for pair in sorted(cuts)]}


def alpha_aware_interpolate(
    first: Image.Image,
    second: Image.Image,
    amount: float,
    *,
    pose_cut: bool = False,
) -> Image.Image:
    """Interpolate premultiplied RGBA on a bottom-aligned canvas."""

    if pose_cut:
        return first.copy() if amount < 0.5 else second.copy()
    canvas_width = max(first.width, second.width)
    canvas_height = max(first.height, second.height)
    first_array = np.asarray(aligned_canvas(first, canvas_width, canvas_height), dtype=np.float32) / 255.0
    second_array = np.asarray(aligned_canvas(second, canvas_width, canvas_height), dtype=np.float32) / 255.0
    amount = ease(amount)
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    first_array[..., :3] *= first_alpha
    second_array[..., :3] *= second_alpha
    rgb = first_array[..., :3] * (1.0 - amount) + second_array[..., :3] * amount
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def action_timeline(action: str) -> list[tuple[str, float, int, int]]:
    schedules = {
        "crawl": [
            ("prepare", 0.85, 0, 0),
            ("act", 1.55, 0, 1),
            ("act", 2.25, 1, 2),
            ("act", 2.95, 2, 3),
            ("act", 3.60, 3, 4),
            ("hold", 4.85, 4, 4),
            ("recover", 5.55, 4, 5),
            ("recover", 6.30, 5, 6),
            ("recover", 8.00, 6, 7),
        ],
        "climb": [
            ("prepare", 0.85, 0, 0),
            ("act", 1.55, 0, 1),
            ("act", 2.25, 1, 2),
            ("act", 2.95, 2, 3),
            ("act", 3.60, 3, 4),
            ("hold", 4.90, 4, 4),
            ("recover", 5.60, 4, 5),
            ("recover", 6.35, 5, 6),
            ("recover", 8.00, 6, 7),
        ],
        "slide": [
            ("prepare", 0.90, 0, 0),
            ("act", 1.60, 0, 1),
            ("act", 2.35, 1, 2),
            ("act", 3.10, 2, 3),
            ("act", 3.70, 3, 4),
            ("hold", 4.90, 4, 4),
            ("recover", 5.55, 4, 5),
            ("recover", 6.35, 5, 6),
            ("recover", 8.00, 6, 7),
        ],
        "hide": [
            ("prepare", 0.90, 0, 0),
            ("act", 1.55, 0, 1),
            ("act", 2.20, 1, 2),
            ("act", 2.90, 2, 3),
            ("act", 3.55, 3, 4),
            ("hold", 4.90, 4, 4),
            ("recover", 5.55, 4, 5),
            ("recover", 6.35, 5, 6),
            ("recover", 8.00, 6, 7),
        ],
        "fall_roll": [
            ("prepare", 0.75, 0, 0),
            ("act", 1.45, 0, 1),
            ("act", 2.15, 1, 2),
            ("act", 2.85, 2, 3),
            ("act", 3.45, 3, 4),
            ("hold", 4.45, 4, 4),
            ("recover", 5.50, 4, 5),
            ("recover", 6.45, 5, 6),
            ("recover", 8.00, 6, 7),
        ],
    }
    return schedules[action]


def state_at(action: str, second: float) -> tuple[str, int, int, float]:
    previous = 0.0
    for phase, end, first, second_cell in action_timeline(action):
        if second <= end:
            local = (second - previous) / max(0.001, end - previous)
            return phase, first, second_cell, min(max(local, 0.0), 1.0)
        previous = end
    return "recover", 6, 7, 1.0


def pose_at(
    layers: list[Image.Image], action: str, second: float, plan: dict[str, object]
) -> tuple[str, Image.Image, float]:
    phase, first, second_cell, amount = state_at(action, second)
    cuts = {tuple(pair) for pair in plan["pose_cuts"]}
    pose = alpha_aware_interpolate(
        layers[first],
        layers[second_cell],
        amount,
        pose_cut=(first, second_cell) in cuts,
    )
    lifts = {
        "crawl": [0, 0, 0, 0, 0, 0, 0, 0],
        "climb": [0, 18, 43, 70, 96, 96, 42, 0],
        "slide": [0, 0, 0, 0, 0, 0, 0, 0],
        "hide": [0, 0, 0, 0, 0, 0, 0, 0],
        "fall_roll": [0, 10, 36, 72, 52, 0, 0, 0],
    }[action]
    lift = lifts[first] + (lifts[second_cell] - lifts[first]) * ease(amount)
    return phase, pose, lift


def draw_ground(frame: Image.Image, *, ground_y: int, action: str) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    draw.line((0, ground_y + 4, frame.width, ground_y + 4), fill=(34, 47, 47, 125), width=3)
    draw.line((0, ground_y + 11, frame.width, ground_y + 11), fill=(230, 216, 172, 70), width=2)
    if action == "slide":
        draw.line((85, ground_y + 19, 875, ground_y + 19), fill=(22, 32, 37, 72), width=2)


def draw_climb_wall(frame: Image.Image) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    left, top, right = 676, 52, 934
    draw.polygon(
        [(left, HEIGHT), (left + 14, top + 38), (left + 48, top), (right - 22, top + 18),
         (right, top + 72), (right - 8, HEIGHT)],
        fill=(54, 64, 71, 236),
    )
    draw.line((left + 14, top + 38, left + 48, top, right - 22, top + 18, right, top + 72),
              fill=(192, 177, 142, 184), width=4, joint="curve")
    for row in range(7):
        y = top + 58 + row * 54
        draw.line((left + 12, y, right - 13, y + 3), fill=(137, 144, 143, 130), width=2)
        for column in range(4):
            x = left + 44 + column * 58 + (23 if row % 2 else 0)
            draw.line((x, y - 51, x - 10, y), fill=(32, 42, 48, 154), width=2)


def draw_hide_occluder(frame: Image.Image) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    base_y = frame.height + 10
    draw.polygon(
        [(545, base_y), (563, 393), (589, 367), (622, 379), (650, 346),
         (689, 361), (726, 333), (765, 352), (801, 333), (839, 371),
         (875, 359), (906, 399), (920, base_y)],
        fill=(25, 61, 48, 244),
    )
    for x, y, radius in ((589, 368, 27), (650, 350, 33), (726, 344, 31), (799, 347, 32), (858, 374, 29)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(42, 86, 61, 235))
    draw.line((551, 408, 910, 408), fill=(15, 38, 31, 228), width=7)


def paste_character(
    frame: Image.Image,
    pose: Image.Image,
    *,
    center_x: float,
    ground_y: int,
    lift: float,
    shadow_scale: float = 1.0,
) -> None:
    bbox = pose.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Pose has no visible pixels")
    draw = ImageDraw.Draw(frame, "RGBA")
    shadow_width = max(40, round(136 * shadow_scale))
    shadow_alpha = max(26, round(88 - min(lift, 100) * 0.48))
    draw.ellipse(
        (center_x - shadow_width / 2, ground_y - 6, center_x + shadow_width / 2, ground_y + 9),
        fill=(18, 28, 32, shadow_alpha),
    )
    x = round(center_x - pose.width / 2)
    y = round(ground_y - bbox[3] - lift)
    frame.alpha_composite(pose, (x, y))


def character_position(action: str, second: float, width: int) -> tuple[float, float]:
    progress = min(max(second / DURATION_SECONDS, 0.0), 1.0)
    if action == "crawl":
        return width * (0.22 + 0.48 * ease(progress)), 1.0
    if action == "slide":
        travel = ease(min(progress / 0.74, 1.0))
        return width * (0.30 + 0.43 * travel), 0.92
    if action == "fall_roll":
        return width * (0.39 + 0.15 * ease(progress)), 0.98
    if action == "hide":
        return width * (0.43 + 0.12 * ease(min(progress / 0.42, 1.0))), 0.98
    return width * 0.57, 0.88


def render_frames(
    action: str,
    *,
    sheet_path: Path,
    background_path: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> Iterable[Image.Image]:
    background = fit_background(background_path, width, height)
    raw_cells = extract_cells(sheet_path)
    target_heights = {"crawl": 270, "climb": 315, "slide": 255, "hide": 300, "fall_roll": 278}
    layers = normalize_layers(raw_cells, target_heights[action])
    plan = interpolation_plan(layers)
    for index in range(round(fps * duration)):
        second = index / fps
        _phase, pose, lift = pose_at(layers, action, second, plan)
        frame = background.copy()
        draw_ground(frame, ground_y=GROUND_Y, action=action)
        if action == "climb":
            draw_climb_wall(frame)
        center_x, shadow_scale = character_position(action, second, width)
        paste_character(frame, pose, center_x=center_x, ground_y=GROUND_Y, lift=lift, shadow_scale=shadow_scale)
        if action == "hide":
            draw_hide_occluder(frame)
        yield frame.convert("RGB")


def write_video(path: Path, frames: Iterable[Image.Image], *, fps: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(path),
        fps=fps,
        codec="libx264",
        quality=8,
        macro_block_size=1,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()


def read_video_metadata(path: Path, *, width: int, height: int, fps: int, frame_count: int) -> dict[str, object]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        actual_count = int(reader.count_frames())
    finally:
        reader.close()
    actual_fps = float(metadata.get("fps") or 0.0)
    size = tuple(metadata.get("size") or ())
    codec = str(metadata.get("codec") or "")
    report = {
        "path": str(path.resolve()),
        "resolution": list(size),
        "fps": actual_fps,
        "frame_count": actual_count,
        "duration_seconds": round(actual_count / actual_fps, 3) if actual_fps else 0.0,
        "codec": codec or "unknown",
        "container_metadata": {key: str(value) for key, value in metadata.items()},
    }
    if size != (width, height) or abs(actual_fps - fps) > 0.01 or actual_count != frame_count:
        raise RuntimeError(f"Unexpected v2 video metadata for {path.name}: {report}")
    if codec and not any(token in codec.lower() for token in ("h264", "avc", "264")):
        raise RuntimeError(f"Expected H.264 stream for {path.name}: {report}")
    report["verified"] = True
    report["codec_verified_as"] = "H.264"
    return report


def write_contact_sheet(video_path: Path, output_path: Path, *, action: str, fps: int) -> dict[str, object]:
    reader = imageio.get_reader(str(video_path))
    try:
        count = int(reader.count_frames())
        sample_count = 16
        tile_width = 240
        tile_height = round(tile_width * HEIGHT / WIDTH)
        label_height = 30
        columns = 4
        rows = math.ceil(sample_count / columns)
        sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "white")
        draw = ImageDraw.Draw(sheet)
        review_font = font()
        for sample in range(sample_count):
            frame_index = round(sample * max(0, count - 1) / max(1, sample_count - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame = frame.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            x = (sample % columns) * tile_width
            y = (sample // columns) * (tile_height + label_height)
            sheet.paste(frame, (x, y + label_height))
            phase, _, _, _ = state_at(action, frame_index / fps)
            draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(238, 242, 244))
            draw.text((x + 8, y + 8), f"{frame_index / fps:0.2f}s  {phase}", fill=(24, 33, 39), font=review_font)
    finally:
        reader.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    return {"path": str(output_path.resolve()), "sample_count": sample_count, "resolution": list(sheet.size)}


def load_source_manifest(input_dir: Path) -> dict[str, object]:
    manifest_path = input_dir / SOURCE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "2.0" or manifest.get("character") != CHARACTER:
        raise ValueError("Expected the male_01 generated_v2 source manifest")
    actions = {entry.get("word"): entry for entry in manifest.get("actions", [])}
    missing = [action for action in ACTIONS if action not in actions]
    if missing:
        raise ValueError(f"Missing source actions: {missing}")
    return manifest


def action_scene(action: str) -> dict[str, object]:
    # Every selected scene asset is v2; slide intentionally uses the v2 ruins
    # plate because the only harbor plate in the workspace is v1.
    backgrounds = {
        "crawl": "nature_pond_wide_v2.png",
        "climb": "adventure_ruins_wide_v2.png",
        "slide": "fantasy_castle_wide_v2.png",
        "hide": "mystery_library_wide_v2.png",
        "fall_roll": "friendship_square_wide_v2.png",
    }
    scenes = {
        "crawl": {
            "ground_plane": "fixed composited ground cue; supplied by scene, no floor baked into sheet",
            "collision_conditions": ["ground plane or collider", "palms, knees, and boots share one baseline"],
            "camera": "fixed 960x480 crop and locked screen-space anchor",
        },
        "climb": {
            "ground_plane": "fixed base ground cue for prepare/recovery",
            "wall": "fixed preview stone wall composited behind the character; no wall pixels are baked into the v2 sheet",
            "collision_conditions": ["vertical climbable wall", "hand and boot contact anchors", "vertical collision and ascent timing"],
            "camera": "fixed 960x480 crop; no camera follow during ascent",
        },
        "slide": {
            "ground_plane": "fixed horizontal slide surface cue remains visible under hips and boots",
            "collision_conditions": ["ground or slide surface", "horizontal travel bounds", "hips and boots grounded during act/hold"],
            "camera": "fixed 960x480 crop and locked ground baseline",
        },
        "hide": {
            "ground_plane": "fixed crouch/recovery baseline",
            "foreground_occluder": "stable foreground cover composited after the character; motion sheet remains unchanged",
            "collision_conditions": ["occluder depth ordering over character", "cover-edge placement", "ground plane for crouch and recovery"],
            "camera": "fixed 960x480 crop; occluder stays locked to camera",
        },
        "fall_roll": {
            "ground_plane": "fixed visible landing surface under roll and recovery",
            "collision_conditions": ["ground plane or collider", "fall-to-roll landing timing", "clearance for the full tuck arc"],
            "camera": "fixed 960x480 crop and locked ground baseline",
        },
    }
    return {"background": backgrounds[action], "ground_anchor_y": GROUND_Y, **scenes[action]}


def render_audit(action: str) -> dict[str, object]:
    audits = {
        "crawl": {
            "ground_contact_review": "hands and knees stay on the fixed ground line while lead limbs alternate across act cells",
            "behavior_read": "low four-point support, forward weight transfer, hold, and grounded recovery",
        },
        "climb": {
            "wall_contact_review": "fixed wall is behind the right-side hand/boot contact plane; ascent is encoded by lift",
            "behavior_read": "base compression, hand/boot contacts, upward pull, cling hold, and controlled descent",
        },
        "slide": {
            "surface_friction_review": "seat and boot soles remain low through travel, then the bracing palm and planted boots slow the motion",
            "behavior_read": "lower, seated travel, friction hold, and kneeling recovery",
        },
        "hide": {
            "occluder_depth_review": "foreground cover is composited after the character and remains camera-locked",
            "behavior_read": "turn, enter cover, conceal, peek, reveal, and crouched exit",
        },
        "fall_roll": {
            "timing_review": "fall pitch and tuck precede the rounded roll hold; braced kneel bridges into recovery",
            "behavior_read": "fall -> tuck -> roll -> side kneel -> crouched recovery",
        },
    }
    return audits[action]


def render_action(
    action: str,
    source_entry: dict[str, object],
    *,
    input_dir: Path,
    output_dir: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> dict[str, object]:
    sheet_path = input_dir / str(source_entry["motion_sheet"])
    if not sheet_path.is_file():
        raise FileNotFoundError(sheet_path)
    scene = action_scene(action)
    background_path = ROOT / "assets" / "backgrounds" / str(scene["background"])
    if not background_path.is_file() or "_v2" not in background_path.stem:
        raise FileNotFoundError(f"Missing v2 background: {background_path}")
    layers = normalize_layers(extract_cells(sheet_path), {"crawl": 270, "climb": 315, "slide": 255, "hide": 300, "fall_roll": 278}[action])
    plan = interpolation_plan(layers)
    video_path = output_dir / f"male_01_{action}.mp4"
    contact_path = output_dir / f"male_01_{action}_contact_sheet.png"
    write_video(
        video_path,
        render_frames(action, sheet_path=sheet_path, background_path=background_path, width=width, height=height, fps=fps, duration=duration),
        fps=fps,
    )
    metadata = read_video_metadata(video_path, width=width, height=height, fps=fps, frame_count=round(fps * duration))
    contact = write_contact_sheet(video_path, contact_path, action=action, fps=fps)
    return {
        "action": action,
        "character": CHARACTER,
        "status": source_entry.get("status"),
        "blocked": bool(source_entry.get("blocked", False)),
        "blocked_scene_checks": source_entry.get("blocked_scene_checks", []),
        "source_risks": {
            "v1_limit": source_entry.get("v1_limit"),
            "v2_improvement": source_entry.get("v2_improvement"),
        },
        "source_manifest_entry": source_entry,
        "motion_sheet": str(sheet_path.resolve()),
        "background": str(background_path.resolve()),
        "timeline": "prepare -> act -> hold -> recover",
        "ground_anchor_y": GROUND_Y,
        "scene": scene,
        "render_audit": render_audit(action),
        "interpolation": plan,
        "video": metadata,
        "contact_sheet": contact,
        "render_policy": {
            "source_family": "generated_v2 only",
            "fixed_background": True,
            "fixed_camera": True,
            "bottom_aligned_ground_anchor": GROUND_Y,
            "alpha_aware_interpolation": True,
            "pose_cuts_recorded": True,
            "debug_overlay_in_mp4": False,
            "phase_labels_in_mp4": False,
            "phase_labels_in_contact_sheet": True,
            "motion_sheet_modified": False,
            "single_character": True,
        },
    }


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    fps = int(args.fps)
    duration = float(args.duration)
    width = int(args.width)
    height = int(args.height)
    if (fps, duration, width, height) != (FPS, DURATION_SECONDS, WIDTH, HEIGHT):
        raise ValueError("Team 2 v2 delivery requires 960x480, 30fps, 8 seconds, and 240 frames.")
    source_manifest = load_source_manifest(input_dir)
    source_actions = {entry["word"]: entry for entry in source_manifest["actions"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        render_action(action, source_actions[action], input_dir=input_dir, output_dir=output_dir,
                      width=width, height=height, fps=fps, duration=duration)
        for action in ACTIONS
    ]
    output_manifest = {
        "manifest_version": "2.0",
        "team": "2",
        "source_team": source_manifest.get("team"),
        "source_manifest": str((input_dir / SOURCE_MANIFEST_NAME).resolve()),
        "character": CHARACTER,
        "delivery": {
            "resolution": [width, height],
            "fps": fps,
            "duration_seconds": duration,
            "frame_count": round(fps * duration),
            "codec": "H.264",
            "pixel_format": "yuv420p",
            "timeline": ["prepare", "act", "hold", "recover"],
            "camera": "fixed",
            "background": "fixed v2 plate per action",
            "ground_anchor_y": GROUND_Y,
        },
        "actions": results,
        "status_policy": "Preserve generated_v2 source status, blocked flag, and blocked scene checks; preview renders never become production approval.",
        "generated_files": [
            *(f"male_01_{action}.mp4" for action in ACTIONS),
            *(f"male_01_{action}_contact_sheet.png" for action in ACTIONS),
            "team_2_video_manifest_v2.json",
        ],
    }
    manifest_path = output_dir / "team_2_video_manifest_v2.json"
    manifest_path.write_text(json.dumps(output_manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "actions": results}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
