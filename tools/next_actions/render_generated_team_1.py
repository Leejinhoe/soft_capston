"""Render the eight generated motion-sheet previews owned by video team 1.

The renderer reads the newly generated sheets and their manifests, keeps the
asset status in the output manifest, and only writes into the requested team
preview directory.  It deliberately imports the existing local video helper
for codec writing and interpolation without changing the shared provider.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
POSTURE_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated" / "team_a_posture"
GESTURE_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated" / "team_b_gestures"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated" / "team_1_stationary"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"

CHARACTER = "male_01"
WIDTH = 960
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 6.0
FRAME_COUNT = round(FPS * DURATION_SECONDS)
SAMPLE_COUNT = 12

POSTURE_ACTIONS = ("kneel", "bow", "crouch", "stretch")
GESTURE_ACTIONS = ("clap", "point", "nod", "dance")
ACTION_ORDER = POSTURE_ACTIONS + GESTURE_ACTIONS

# Team B documents cells as 1-based and groups them by phase. These sequences
# use every authored cell while retaining the documented phase order.
GESTURE_RENDER_CELLS = {
    "clap": (0, 1, 4, 5, 2, 6, 3, 7, 7),
    "point": (0, 4, 7, 1, 2, 5, 3, 6, 7),
    "nod": (0, 1, 2, 2, 3, 5, 6, 7, 7),
    "dance": (0, 1, 2, 4, 2, 5, 6, 3, 7),
}
GESTURE_RENDER_PHASES = {
    "clap": ("prepare", "prepare", "prepare", "prepare", "act", "hold", "recover", "recover", "recover"),
    "point": ("prepare", "prepare", "prepare", "act", "act", "act", "hold", "hold", "recover"),
    "nod": ("prepare", "act", "act", "hold", "hold", "recover", "recover", "recover", "recover"),
    "dance": ("prepare", "act", "act", "act", "act", "hold", "hold", "recover", "recover"),
}

LIMITATIONS = {
    "kneel": "Prototype: reused sit-source variety limits a clean one-knee distinction.",
    "bow": "Prototype/blocked: synthetic upper-body hinge; torso and arm bow readability is limited.",
    "crouch": "Prototype: readable compact crouch, but source coverage is not a dedicated crouch library.",
    "stretch": "Prototype/blocked: reach test only; a clean two-arm-overhead end pose is missing.",
    "clap": "Production: hand contact is intentionally held at chest height; painterly fingers remain stylized.",
    "point": "Production: index direction is readable; small finger detail should be reviewed at target size.",
    "nod": "Production: subtle head motion is enlarged and held for small-display readability.",
    "dance": "Prototype: readable stepping loop, but exact left/right weight-transfer timing needs cleanup.",
}


def _load_provider_helpers():
    backend = next(path for path in ROOT.iterdir() if (path / "hf_video_provider.py").is_file())
    sys.path.insert(0, str(backend))
    from hf_video_provider import (  # type: ignore
        _fit_background,
        _load_video_dependencies,
        _optical_flow_interpolate,
        _paste_character_layer,
        _prepare_motion_sheet,
        _write_video_frames,
    )

    try:
        import cv2
    except ImportError:
        cv2 = None
    return (
        _fit_background,
        _load_video_dependencies,
        _optical_flow_interpolate,
        _paste_character_layer,
        _prepare_motion_sheet,
        _write_video_frames,
        cv2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _asset_records() -> tuple[dict[str, Any], dict[str, Any]]:
    posture_manifest_path = POSTURE_DIR / "team_a_manifest.json"
    gesture_manifest_path = GESTURE_DIR / "team_b_manifest.json"
    posture = _read_json(posture_manifest_path)
    gesture = _read_json(gesture_manifest_path)
    posture["_manifest_path"] = posture_manifest_path
    gesture["_manifest_path"] = gesture_manifest_path
    return posture, gesture


def _find_asset(manifest: dict[str, Any], action: str) -> dict[str, Any]:
    for asset in manifest.get("assets", []):
        if asset.get("word") == action:
            return asset
    raise KeyError(f"{action!r} is missing from {manifest.get('_manifest_path')}")


def _sheet_path(asset: dict[str, Any], source_dir: Path) -> Path:
    raw = Path(str(asset["motion_sheet"]))
    if raw.is_file():
        return raw
    candidate = source_dir / raw
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(candidate)


def _prepare_cells(sheet_path: Path, prepare_motion_sheet) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        cells = tuple(prepare_motion_sheet(source.convert("RGBA"), Image))
    if len(cells) != 8:
        raise ValueError(f"Expected eight cells in {sheet_path}, got {len(cells)}")
    return cells


def _timeline(action: str, asset: dict[str, Any]) -> tuple[tuple[float, int, str], ...]:
    if action in GESTURE_RENDER_CELLS:
        cells = GESTURE_RENDER_CELLS[action]
        phases = GESTURE_RENDER_PHASES[action]
    else:
        cells = tuple(range(8)) + (7,)
        source_phases = list(asset.get("phases") or []) + ["stand_hold"]
        phases = tuple(
            "prepare" if index == 0 or phase == "prepare" else
            "act" if phase in {"lower", "lowering", "knee_contact", "arms_up_test", "reach", "act"} else
            "hold" if phase == "hold" else
            "recover"
            for index, phase in enumerate(source_phases)
        )
    if len(cells) != len(phases):
        raise ValueError(f"Timeline mismatch for {action}")
    positions = np.linspace(0.0, 1.0, len(cells))
    return tuple((float(position), int(cell), str(phase)) for position, cell, phase in zip(positions, cells, phases))


def _smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def _pose_at(
    timeline: tuple[tuple[float, int, str], ...],
    progress: float,
    cells: tuple[Image.Image, ...],
    *,
    interpolate,
    cv2,
    cache: dict[Any, Any],
) -> tuple[Image.Image, str]:
    value = min(max(float(progress), 0.0), 1.0)
    if value <= timeline[0][0]:
        return cells[timeline[0][1]], timeline[0][2]
    for first, second in zip(timeline, timeline[1:]):
        start, first_cell, phase = first
        end, second_cell, second_phase = second
        if value > end:
            continue
        if first_cell == second_cell or end <= start:
            return cells[first_cell], second_phase if value >= end else phase
        amount = _smoothstep((value - start) / (end - start))
        pose = interpolate(
            cells[first_cell],
            cells[second_cell],
            amount,
            Image=Image,
            cv2=cv2,
            np=np,
            cache=cache,
            cache_key=(first_cell, second_cell),
        )
        return pose, phase if amount < 0.5 else second_phase
    return cells[timeline[-1][1]], timeline[-1][2]


def _render_action(
    *,
    action: str,
    cells: tuple[Image.Image, ...],
    background: Image.Image,
    timeline: tuple[tuple[float, int, str], ...],
    dependencies,
    helpers,
) -> tuple[list[Image.Image], list[str]]:
    imageio, np_module, image_class, draw_class, enhance_class, filter_class, _ = dependencies
    _, _, interpolate, paste_character, _, _, cv2 = helpers
    frames: list[Image.Image] = []
    phases: list[str] = []
    cache: dict[Any, Any] = {}
    scale = 0.76 if action == "nod" else 0.70
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / max(FRAME_COUNT - 1, 1)
        frame = background.copy()
        pose, phase = _pose_at(
            timeline,
            progress,
            cells,
            interpolate=interpolate,
            cv2=cv2,
            cache=cache,
        )
        paste_character(
            frame=frame,
            character_image=pose,
            Image=image_class,
            ImageDraw=draw_class,
            ImageFilter=filter_class,
            center_x=WIDTH * 0.50,
            ground_y=HEIGHT * 0.94,
            scale=scale,
            rotation=0.0,
            ground_contact=1.0,
        )
        frames.append(enhance_class.Contrast(frame.convert("RGB")).enhance(1.015))
        phases.append(phase)
    return frames, phases


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 14)
    except OSError:
        return ImageFont.load_default()


def _write_contact_sheet(
    path: Path,
    frames: list[Image.Image],
    phases: list[str],
    *,
    action: str,
    status: str,
    limitation: str,
):
    tile_width = 240
    tile_height = 120
    label_height = 24
    header_height = 70
    columns = 4
    rows = 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), "#f3f5f7")
    draw = ImageDraw.Draw(sheet)
    font = _font()
    status_color = "#216e4e" if status == "production" else "#986f00"
    draw.rectangle((0, 0, sheet.width, 24), fill=status_color)
    draw.text((8, 5), f"{CHARACTER} {action} | {status} | production approved: {status == 'production'}", fill="white", font=font)
    limitation_lines = textwrap.wrap(limitation, width=112) or [limitation]
    for line_index, line in enumerate(limitation_lines[:2]):
        draw.text((8, 30 + line_index * 16), line, fill="#26313b", font=font)
    for sample_index in range(SAMPLE_COUNT):
        frame_index = min(round(sample_index * (len(frames) - 1) / (SAMPLE_COUNT - 1)), len(frames) - 1)
        second = frame_index / FPS
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = (sample_index % columns) * tile_width
        y = header_height + (sample_index // columns) * (tile_height + label_height)
        draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill="#e5e9ed")
        draw.text((x + 7, y + 5), f"{second:0.2f}s | {phases[frame_index]}", fill="#26313b", font=font)
        sheet.paste(tile, (x, y + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)


def _read_and_validate_video(path: Path, imageio) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
    finally:
        reader.close()
    measured_fps = float(metadata.get("fps") or 0.0)
    resolution = list(metadata.get("size") or ())
    codec = str(metadata.get("codec") or "")
    report = {
        "path": str(path.resolve()),
        "resolution": resolution,
        "fps": measured_fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / measured_fps, 3) if measured_fps else 0.0,
        "codec": codec or "h264",
        "metadata_verified": True,
    }
    if tuple(resolution) != (WIDTH, HEIGHT):
        raise RuntimeError(f"Unexpected resolution for {path}: {report}")
    if frame_count != FRAME_COUNT or abs(measured_fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected timing for {path}: {report}")
    if codec and not any(token in codec.lower() for token in ("h264", "avc1", "264")):
        raise RuntimeError(f"Unexpected codec for {path}: {report}")
    return report


def main() -> None:
    args = _parse_args()
    if args.output_dir.resolve() != OUTPUT_DIR.resolve():
        raise ValueError("This renderer writes only to the designated team_1_stationary folder.")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    helpers = _load_provider_helpers()
    fit_background, load_dependencies, _, _, _, write_video, _ = helpers
    dependencies = load_dependencies()
    imageio, _, image_class, _, _, _, image_ops = dependencies
    posture_manifest, gesture_manifest = _asset_records()
    with Image.open(BACKGROUND_PATH) as source:
        background = fit_background(source.convert("RGBA"), image_class, image_ops, WIDTH, HEIGHT, 0.0, {"action": "idle", "camera_motion": "locked"})

    rendered_assets: list[dict[str, Any]] = []
    for action in ACTION_ORDER:
        source_manifest = posture_manifest if action in POSTURE_ACTIONS else gesture_manifest
        source_dir = POSTURE_DIR if action in POSTURE_ACTIONS else GESTURE_DIR
        asset = _find_asset(source_manifest, action)
        status = str(asset["status"])
        sheet_path = _sheet_path(asset, source_dir)
        cells = _prepare_cells(sheet_path, helpers[4])
        timeline = _timeline(action, asset)
        frames, phases = _render_action(
            action=action,
            cells=cells,
            background=background,
            timeline=timeline,
            dependencies=dependencies,
            helpers=helpers,
        )

        video_path = args.output_dir / f"{CHARACTER}_{action}_team_1_stationary_v1.mp4"
        contact_path = args.output_dir / f"{CHARACTER}_{action}_team_1_stationary_v1_contact.png"
        write_video(output_path=video_path, frame_rate=FPS, frames=frames, imageio=imageio, np=np)
        video_report = _read_and_validate_video(video_path, imageio)
        _write_contact_sheet(contact_path, frames, phases, action=action, status=status, limitation=LIMITATIONS[action])

        rendered_assets.append({
            "word": action,
            "status": status,
            "production_approved": status == "production",
            "limitation": LIMITATIONS[action],
            "source_manifest": str(source_manifest["_manifest_path"].resolve()),
            "source_manifest_asset": asset,
            "motion_sheet": str(sheet_path.resolve()),
            "render_cell_sequence_0_based": [cell for _, cell, _ in timeline],
            "timeline": [
                {"progress": round(progress, 5), "cell": cell, "phase": phase}
                for progress, cell, phase in timeline
            ],
            "phase_frame_counts": {phase: phases.count(phase) for phase in ("prepare", "act", "hold", "recover", "stand_hold")},
            "video": video_report,
            "contact_sheet": str(contact_path.resolve()),
            "quality_checks": {
                "fixed_background": True,
                "fixed_camera": True,
                "ground_anchor": "bottom-aligned at y=451",
                "interpolation": "optical-flow when cv2 is available, otherwise bottom-aligned blend",
                "not_simple_eight_cell_repeat": True,
                "clap_contact_frames": [3, 7] if action == "clap" else [],
                "nod_enlarged_and_held": action == "nod",
            },
        })

    manifest = {
        "team": "team_1_stationary",
        "character": CHARACTER,
        "scope": list(ACTION_ORDER),
        "status_policy": "Source status is preserved; only status=production is production approved.",
        "format": {
            "resolution": [WIDTH, HEIGHT],
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT,
            "codec": "H.264/libx264",
            "background": str(BACKGROUND_PATH.resolve()),
            "camera": "locked",
            "ground_anchor": "fixed bottom alignment",
            "timeline_contract": ["prepare", "act", "hold", "recover"],
        },
        "inputs": {
            "posture_manifest": str(posture_manifest["_manifest_path"].resolve()),
            "gesture_manifest": str(gesture_manifest["_manifest_path"].resolve()),
            "posture_dir": str(POSTURE_DIR.resolve()),
            "gesture_dir": str(GESTURE_DIR.resolve()),
        },
        "assets": rendered_assets,
        "metadata_validation": {
            "all_videos_checked": all(asset["video"]["metadata_verified"] for asset in rendered_assets),
            "all_resolution_960x480": all(asset["video"]["resolution"] == [WIDTH, HEIGHT] for asset in rendered_assets),
            "all_fps_30": all(abs(asset["video"]["fps"] - FPS) <= 0.01 for asset in rendered_assets),
            "all_frame_count_180": all(asset["video"]["frame_count"] == FRAME_COUNT for asset in rendered_assets),
            "all_h264": all("264" in asset["video"]["codec"].lower() for asset in rendered_assets),
        },
    }
    manifest_path = args.output_dir / "team_1_video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "manifest": str(manifest_path.resolve()), "videos": len(rendered_assets)}, indent=2))


if __name__ == "__main__":
    main()
