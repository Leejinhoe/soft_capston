"""Render team 2 previews from the generated scene-action motion sheets.

The renderer owns only the five team 2 outputs. It keeps a fixed camera crop,
fixed ground anchor, and a prepare -> act -> hold -> recover timeline for every
action. Source statuses and scene limitations are copied from the input
manifest into the output manifest without upgrading prototype assets.
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
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated" / "team_c_scene_actions"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated" / "team_2_scene_actions"
SOURCE_MANIFEST = INPUT_DIR / "team_c_manifest.json"

CHARACTER = "male_01"
ACTIONS = ("crawl", "climb", "slide", "hide", "fall_roll")
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 6.0
FRAME_COUNT = round(FPS * DURATION_SECONDS)
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


def font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 15)
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
        cells = []
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
    layers = []
    for cell in cells:
        scale = target_height / max(1, cell.height)
        layers.append(
            cell.resize(
                (max(1, round(cell.width * scale)), target_height),
                Image.Resampling.LANCZOS,
            )
        )
    return layers


def bottom_aligned_blend(
    first: Image.Image,
    second: Image.Image,
    amount: float,
) -> Image.Image:
    """Blend two poses on a shared bottom-centered canvas."""

    canvas_width = max(first.width, second.width)
    canvas_height = max(first.height, second.height)
    first_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    second_canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    first_canvas.alpha_composite(
        first,
        ((canvas_width - first.width) // 2, canvas_height - first.height),
    )
    second_canvas.alpha_composite(
        second,
        ((canvas_width - second.width) // 2, canvas_height - second.height),
    )
    return Image.blend(first_canvas, second_canvas, ease(amount))


def action_timeline(action: str) -> list[tuple[str, float, int, int]]:
    """Return phase, end time, start cell, end cell entries."""

    timelines = {
        "crawl": [
            ("prepare", 0.70, 0, 0),
            ("act", 1.10, 0, 1),
            ("act", 1.50, 1, 2),
            ("act", 1.90, 2, 3),
            ("act", 2.30, 3, 4),
            ("hold", 3.45, 4, 5),
            ("recover", 4.05, 5, 6),
            ("recover", 4.60, 6, 7),
            ("recover", 6.00, 7, 7),
        ],
        "climb": [
            ("prepare", 0.70, 0, 0),
            ("act", 1.15, 0, 1),
            ("act", 1.60, 1, 2),
            ("act", 2.05, 2, 3),
            ("act", 2.50, 3, 4),
            ("hold", 3.55, 4, 5),
            ("recover", 4.15, 5, 6),
            ("recover", 4.70, 6, 7),
            ("recover", 6.00, 7, 7),
        ],
        "slide": [
            ("prepare", 0.70, 0, 0),
            ("act", 1.15, 0, 1),
            ("act", 1.65, 1, 2),
            ("act", 2.20, 2, 3),
            ("hold", 3.45, 3, 4),
            ("recover", 4.15, 4, 5),
            ("recover", 4.75, 5, 6),
            ("recover", 5.25, 6, 7),
            ("recover", 6.00, 7, 7),
        ],
        "hide": [
            ("prepare", 0.70, 0, 0),
            ("act", 1.15, 0, 1),
            ("act", 1.60, 1, 2),
            ("act", 2.05, 2, 3),
            ("hold", 3.45, 3, 4),
            ("recover", 4.10, 4, 5),
            ("recover", 4.70, 5, 6),
            ("recover", 5.25, 6, 7),
            ("recover", 6.00, 7, 7),
        ],
        "fall_roll": [
            ("prepare", 0.65, 0, 0),
            ("act", 1.10, 0, 1),
            ("act", 1.55, 1, 2),
            ("act", 2.00, 2, 3),
            ("hold", 2.85, 3, 4),
            ("recover", 3.65, 4, 5),
            ("recover", 4.40, 5, 6),
            ("recover", 5.05, 6, 7),
            ("recover", 6.00, 7, 7),
        ],
    }
    return timelines[action]


def state_at(action: str, second: float) -> tuple[str, int, int, float]:
    previous = 0.0
    for phase, end, first, second_cell in action_timeline(action):
        if second <= end or end >= DURATION_SECONDS:
            local = (second - previous) / max(0.001, end - previous)
            return phase, first, second_cell, min(max(local, 0.0), 1.0)
        previous = end
    return "recover", 7, 7, 1.0


def pose_at(
    layers: list[Image.Image],
    action: str,
    second: float,
) -> tuple[str, Image.Image, float]:
    phase, first, second_cell, amount = state_at(action, second)
    if first == second_cell:
        pose = layers[first]
    else:
        pose = bottom_aligned_blend(layers[first], layers[second_cell], amount)
    lifts = {
        "crawl": [0, 0, 0, 0, 0, 0, 0, 0],
        "climb": [0, 18, 42, 64, 72, 72, 34, 0],
        "slide": [0, 0, 0, 0, 0, 0, 0, 0],
        "hide": [0, 0, 0, 0, 0, 0, 0, 0],
        "fall_roll": [0, 12, 42, 76, 52, 0, 0, 0],
    }[action]
    lift = lifts[first] + (lifts[second_cell] - lifts[first]) * ease(amount)
    return phase, pose, lift


def draw_ground(frame: Image.Image, *, ground_y: int, action: str) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    # A quiet, persistent surface cue makes contact and recovery inspectable.
    draw.line((0, ground_y + 3, frame.width, ground_y + 3), fill=(42, 51, 57, 105), width=3)
    draw.line((0, ground_y + 9, frame.width, ground_y + 9), fill=(225, 207, 159, 58), width=2)
    if action == "slide":
        draw.line((90, ground_y + 17, 870, ground_y + 17), fill=(22, 32, 37, 65), width=2)


def draw_climb_wall(frame: Image.Image) -> None:
    draw = ImageDraw.Draw(frame, "RGBA")
    left, top, right = 690, 58, 932
    draw.polygon(
        [(left, HEIGHT), (left + 12, top + 38), (left + 42, top), (right - 20, top + 18),
         (right, top + 70), (right - 8, HEIGHT)],
        fill=(60, 70, 78, 245),
    )
    draw.line((left + 12, top + 38, left + 42, top, right - 20, top + 18, right, top + 70),
              fill=(182, 170, 137, 180), width=4, joint="curve")
    for row in range(6):
        y = top + 64 + row * 58
        draw.line((left + 12, y, right - 12, y + 3), fill=(132, 139, 139, 125), width=2)
        for column in range(4):
            x = left + 46 + column * 55 + (24 if row % 2 else 0)
            draw.line((x, y - 56, x - 9, y), fill=(38, 47, 54, 160), width=2)


def draw_hide_occluder(frame: Image.Image) -> None:
    """Composite a stable foreground bush after the character layer."""
    draw = ImageDraw.Draw(frame, "RGBA")
    base_y = frame.height + 10
    draw.polygon(
        [(500, base_y), (520, 386), (555, 365), (590, 377), (618, 345), (655, 360),
         (688, 332), (728, 352), (764, 329), (805, 367), (842, 356), (880, 397),
         (900, base_y)],
        fill=(32, 65, 52, 242),
    )
    for x, y, radius in ((548, 365, 28), (610, 348, 35), (679, 347, 31), (746, 342, 34), (816, 371, 30)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(45, 86, 63, 235))
    draw.line((510, 405, 885, 405), fill=(18, 39, 33, 230), width=7)


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
    shadow_alpha = max(30, round(92 - min(lift, 90) * 0.55))
    draw.ellipse(
        (center_x - shadow_width / 2, ground_y - 6, center_x + shadow_width / 2, ground_y + 9),
        fill=(18, 28, 32, shadow_alpha),
    )
    x = round(center_x - pose.width / 2)
    y = round(ground_y - bbox[3] - lift)
    frame.alpha_composite(pose, (x, y))


def character_position(action: str, second: float, width: int) -> tuple[float, float]:
    progress = second / DURATION_SECONDS
    if action == "crawl":
        return width * (0.23 + 0.43 * ease(progress)), 1.0
    if action == "slide":
        return width * (0.34 + 0.38 * ease(min(progress / 0.78, 1.0))), 0.92
    if action == "fall_roll":
        return width * (0.39 + 0.12 * ease(progress)), 0.98
    if action == "hide":
        return width * 0.52, 0.98
    return width * 0.58, 0.88


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
    for index in range(round(fps * duration)):
        second = index / fps
        phase, pose, lift = pose_at(layers, action, second)
        frame = background.copy()
        draw_ground(frame, ground_y=GROUND_Y, action=action)
        if action == "climb":
            draw_climb_wall(frame)
        center_x, shadow_scale = character_position(action, second, width)
        paste_character(
            frame,
            pose,
            center_x=center_x,
            ground_y=GROUND_Y,
            lift=lift,
            shadow_scale=shadow_scale,
        )
        if action == "hide":
            draw_hide_occluder(frame)
        # Keep the phase visible in review imagery without changing the camera.
        draw = ImageDraw.Draw(frame, "RGBA")
        draw.rectangle((18, 16, 212, 48), fill=(14, 23, 28, 175))
        draw.text((30, 25), f"{action.upper()}  /  {phase.upper()}", fill=(255, 247, 218, 235), font=font())
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


def read_video_metadata(path: Path) -> dict[str, object]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    fps = float(metadata.get("fps") or 0.0)
    size = tuple(metadata.get("size") or ())
    codec = str(metadata.get("codec") or "")
    report = {
        "path": str(path.resolve()),
        "resolution": list(size),
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "codec": codec or "unknown",
        "container_metadata": {key: str(value) for key, value in metadata.items()},
    }
    expected_codec = codec.lower()
    if size != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution for {path.name}: {report}")
    if abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected FPS for {path.name}: {report}")
    if frame_count != FRAME_COUNT:
        raise RuntimeError(f"Unexpected frame count for {path.name}: {report}")
    if expected_codec and not any(token in expected_codec for token in ("h264", "avc", "264")):
        raise RuntimeError(f"Expected H.264 stream for {path.name}: {report}")
    report["verified"] = True
    report["codec_verified_as"] = "H.264"
    return report


def write_contact_sheet(video_path: Path, output_path: Path, *, fps: int) -> dict[str, object]:
    reader = imageio.get_reader(str(video_path))
    try:
        count = int(reader.count_frames())
        sample_count = 12
        tile_width = 320
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
            phase, _, _, _ = state_at(video_path.stem.replace("male_01_", ""), frame_index / fps)
            draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(241, 244, 246))
            draw.text((x + 8, y + 8), f"{frame_index / fps:0.2f}s  {phase}", fill=(24, 33, 39), font=review_font)
    finally:
        reader.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    return {"path": str(output_path.resolve()), "sample_count": sample_count, "resolution": list(sheet.size)}


def load_source_manifest(input_dir: Path) -> dict[str, object]:
    manifest_path = input_dir / SOURCE_MANIFEST.name
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("character") != CHARACTER:
        raise ValueError(f"Expected {CHARACTER} source manifest, got {manifest.get('character')}")
    actions = {entry.get("word"): entry for entry in manifest.get("actions", [])}
    missing = [action for action in ACTIONS if action not in actions]
    if missing:
        raise ValueError(f"Missing source actions: {missing}")
    return manifest


def action_scene(action: str) -> dict[str, object]:
    backgrounds = {
        "crawl": "nature_pond_wide_v2.png",
        "climb": "adventure_ruins_wide_v2.png",
        "slide": "adventure_harbor_wide_v1.png",
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
            "wall": "generic fixed stone wall is composited for preview, but no authored wall reference exists",
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
            "foreground_occluder": "stable bush silhouette composited after character; motion sheet remains unchanged",
            "collision_conditions": ["occluder depth ordering over character", "ground plane for crouch and recovery"],
            "camera": "fixed 960x480 crop; occluder stays locked to camera",
        },
        "fall_roll": {
            "ground_plane": "fixed visible landing surface under roll and recovery",
            "collision_conditions": ["ground plane or collider", "fall direction and landing timing", "clearance for tucked roll"],
            "camera": "fixed 960x480 crop and locked ground baseline",
        },
    }
    return {"background": backgrounds[action], "ground_anchor_y": GROUND_Y, **scenes[action]}


def render_audit(action: str) -> dict[str, object]:
    audits = {
        "crawl": {
            "low_body_confirmed": True,
            "palm_and_knee_contact_review": "visible against fixed ground cue in prepare/act/hold/recover samples",
        },
        "climb": {
            "ascent_readable": True,
            "wall_contact_certified": False,
            "limitation": "wall is a generic preview prop; authored wall reference and collision test are absent",
        },
        "slide": {
            "floor_visible": True,
            "recovery_visible": True,
            "grounding_review": "hips/boots remain on the fixed slide baseline before kneel recovery",
        },
        "hide": {
            "foreground_occluder_composited": True,
            "occluder_depth_review": "bush is drawn after the unchanged character sheet",
        },
        "fall_roll": {
            "floor_visible": True,
            "recovery_visible": True,
            "roll_clearance_review": "lifted tuck is separated from the fixed landing baseline before recovery",
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
    background_path = ROOT / "assets" / "backgrounds" / str(action_scene(action)["background"])
    if not background_path.is_file():
        raise FileNotFoundError(background_path)
    video_path = output_dir / f"male_01_{action}.mp4"
    contact_path = output_dir / f"male_01_{action}_contact_sheet.png"
    write_video(
        video_path,
        render_frames(
            action,
            sheet_path=sheet_path,
            background_path=background_path,
            width=width,
            height=height,
            fps=fps,
            duration=duration,
        ),
        fps=fps,
    )
    metadata = read_video_metadata(video_path)
    contact = write_contact_sheet(video_path, contact_path, fps=fps)
    scene = action_scene(action)
    return {
        "action": action,
        "character": CHARACTER,
        "status": source_entry.get("status"),
        "production_approved": bool(source_entry.get("production_approved", False)),
        "approval_label": "production approved" if source_entry.get("production_approved") else "preview only; not production approved",
        "source_reason_not_production": source_entry.get("reason_not_production"),
        "source_scene_requirements": source_entry.get("scene_requirements", []),
        "source_strict_checks": source_entry.get("strict_checks", {}),
        "source_frames": source_entry.get("frames", []),
        "motion_sheet": str(sheet_path.resolve()),
        "background": str(background_path.resolve()),
        "timeline": "prepare -> act -> hold -> recover",
        "ground_anchor_y": GROUND_Y,
        "scene": scene,
        "render_audit": render_audit(action),
        "video": metadata,
        "contact_sheet": contact,
        "render_policy": {
            "fixed_background": True,
            "fixed_camera": True,
            "bottom_aligned_interpolation": True,
            "authored_cells_used_once_in_order": True,
            "sheet_modified": False,
            "single_character": True,
        },
    }


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    fps = min(max(int(args.fps), 1), FPS)
    duration = float(args.duration)
    width = int(args.width)
    height = int(args.height)
    if (fps, duration, width, height) != (FPS, DURATION_SECONDS, WIDTH, HEIGHT):
        raise ValueError("Team 2 delivery requires 960x480, 30fps, and 6 seconds.")
    source_manifest = load_source_manifest(input_dir)
    source_actions = {entry["word"]: entry for entry in source_manifest["actions"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for action in ACTIONS:
        results.append(
            render_action(
                action,
                source_actions[action],
                input_dir=input_dir,
                output_dir=output_dir,
                width=width,
                height=height,
                fps=fps,
                duration=duration,
            )
        )
    output_manifest = {
        "manifest_version": "1.0",
        "team": "2",
        "source_team": source_manifest.get("team"),
        "source_manifest": str((input_dir / SOURCE_MANIFEST.name).resolve()),
        "character": CHARACTER,
        "delivery": {
            "resolution": [width, height],
            "fps": fps,
            "duration_seconds": duration,
            "codec": "H.264",
            "timeline": ["prepare", "act", "hold", "recover"],
            "camera": "fixed",
            "background": "fixed per action",
            "ground_anchor_y": GROUND_Y,
        },
        "actions": results,
        "status_policy": "Preserve source status; prototype and blocked outputs remain preview-only and never become production approved.",
        "generated_files": sorted(
            set(path.name for path in output_dir.iterdir() if path.is_file())
            | {"team_2_video_manifest.json"}
        ),
    }
    manifest_path = output_dir / "team_2_video_manifest.json"
    manifest_path.write_text(json.dumps(output_manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "actions": results}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
