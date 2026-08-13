"""Render prototype video previews for the round4 prop-interaction group.

The renderer consumes only the five assigned 4x2 RGBA motion sheets and their
phase JSON/group manifest. MP4 frames contain the authored scene composites
without labels; labels are limited to the derived contact sheets and overview.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round4" / "agent_01_prop_interactions"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round4" / "agent_01_prop_interactions"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"

CHARACTER = "male_01"
ACTIONS = ("open_chest", "unlock", "pick_up", "lift", "uncover")
PHASE_CONTRACT = ("prepare", "act", "hold", "recover")
WIDTH = 960
HEIGHT = 480
FPS = 30
FRAME_COUNT = 240
DURATION_SECONDS = 8.0
SHEET_COLUMNS = 4
SHEET_ROWS = 2
GROUND_Y = 452
FLOW_MIN_SILHOUETTE_IOU = 0.48

# Full-cell placement keeps baked floor, table, door, and prop composites in
# their authored relation instead of re-centering only the alpha bounds.
SCENE_PROFILES: dict[str, dict[str, float]] = {
    "open_chest": {"scale": 0.86, "center_x": 0.46},
    "unlock": {"scale": 0.84, "center_x": 0.51},
    "pick_up": {"scale": 0.84, "center_x": 0.49},
    "lift": {"scale": 0.88, "center_x": 0.50},
    "uncover": {"scale": 0.85, "center_x": 0.53},
}

# The phase JSONs provide the ordered eight-cell contract but do not contain
# frame durations. These standard round4 beats preserve readable holds.
DEFAULT_PROGRESS = (0.00, 0.12, 0.26, 0.40, 0.56, 0.71, 0.86, 1.00)


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


def font(size: int = 16) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def phase_path(input_dir: Path, key: str) -> Path:
    return input_dir / f"male_01_{key}_cycle_round4_phases.json"


def sheet_path(input_dir: Path, key: str) -> Path:
    return input_dir / f"male_01_{key}_cycle_round4.png"


def contact_source_path(input_dir: Path, key: str) -> Path:
    return input_dir / f"male_01_{key}_cycle_round4_contact.png"


def validate_source_contract(input_dir: Path, group_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {str(item.get("key")): item for item in group_manifest.get("assets", []) if isinstance(item, dict)}
    if tuple(records) != ACTIONS and set(records) != set(ACTIONS):
        raise ValueError(f"Group manifest keys must be exactly {ACTIONS}; got {tuple(records)}")
    contracts: dict[str, dict[str, Any]] = {}
    for key in ACTIONS:
        asset = records[key]
        phase_file = phase_path(input_dir, key)
        sheet_file = sheet_path(input_dir, key)
        contact_file = contact_source_path(input_dir, key)
        if not phase_file.is_file() or not sheet_file.is_file() or not contact_file.is_file():
            raise FileNotFoundError(f"Missing assigned source for {key}")
        phase_json = read_json(phase_file)
        entries = phase_json.get("phase_intent")
        if not isinstance(entries, list) or len(entries) != 8:
            raise ValueError(f"{phase_file} must contain eight phase_intent entries")
        phases = []
        for expected_cell, entry in enumerate(entries, 1):
            if not isinstance(entry, dict) or int(entry.get("cell", -1)) != expected_cell:
                raise ValueError(f"{phase_file} cells must be ordered 1..8")
            phase = str(entry.get("phase", ""))
            if phase not in PHASE_CONTRACT:
                raise ValueError(f"Unexpected phase {phase!r} in {phase_file}")
            phases.append(phase)
        if tuple(phases) != ("prepare", "prepare", "act", "act", "hold", "hold", "recover", "recover"):
            raise ValueError(f"Unexpected four-phase order in {phase_file}: {phases}")
        if str(asset.get("status")) != "prototype" or bool(asset.get("blocked")):
            raise ValueError(f"Source status contract changed for {key}: {asset.get('status')}")
        contracts[key] = {
            "asset": copy.deepcopy(asset),
            "phase_json": phase_json,
            "phase_path": phase_file,
            "sheet_path": sheet_file,
            "source_contact_path": contact_file,
            "phases": phases,
        }
    return contracts


def extract_cells(path: Path) -> tuple[Image.Image, ...]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
        if sheet.size != (1792, 1024) or sheet.mode != "RGBA":
            raise ValueError(f"Expected 1792x1024 RGBA source sheet, got {sheet.size} {sheet.mode}: {path}")
        cells: list[Image.Image] = []
        for index in range(SHEET_COLUMNS * SHEET_ROWS):
            column = index % SHEET_COLUMNS
            row = index // SHEET_COLUMNS
            left = column * sheet.width // SHEET_COLUMNS
            top = row * sheet.height // SHEET_ROWS
            right = (column + 1) * sheet.width // SHEET_COLUMNS
            bottom = (row + 1) * sheet.height // SHEET_ROWS
            cell = sheet.crop((left, top, right, bottom))
            if cell.getchannel("A").getbbox() is None:
                raise ValueError(f"Empty alpha cell {index + 1} in {path}")
            cells.append(cell)
        return tuple(cells)


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    first_mask = np.asarray(first.getchannel("A")) >= 64
    second_mask = np.asarray(second.getchannel("A")) >= 64
    union = np.logical_or(first_mask, second_mask).sum()
    return float(np.logical_and(first_mask, second_mask).sum() / union) if union else 0.0


def interpolate_pose(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    amount = smoothstep(amount)
    first_array = np.asarray(first, dtype=np.float32) / 255.0
    second_array = np.asarray(second, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    # Premultiplied RGB avoids dark fringes around transparent authored edges.
    rgb = first_array[..., :3] * first_alpha * (1.0 - amount)
    rgb += second_array[..., :3] * second_alpha * amount
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def transition_report(cells: tuple[Image.Image, ...], phases: list[str]) -> tuple[list[dict[str, Any]], set[tuple[int, int]]]:
    transitions: list[dict[str, Any]] = []
    cuts: set[tuple[int, int]] = set()
    for index, (first, second) in enumerate(zip(cells, cells[1:])):
        overlap = alpha_iou(first, second)
        phase_boundary = phases[index] != phases[index + 1]
        stateful_hold_change = phases[index] == phases[index + 1] == "hold"
        method = "alpha_aware" if overlap >= FLOW_MIN_SILHOUETTE_IOU and not phase_boundary and not stateful_hold_change else "pose_cut"
        pair = (index, index + 1)
        if method == "pose_cut":
            cuts.add(pair)
        transitions.append({
            "from_cell": index + 1,
            "to_cell": index + 2,
            "silhouette_iou": round(overlap, 4),
            "phase_boundary": phase_boundary,
            "stateful_hold_change": stateful_hold_change,
            "method": method,
        })
    return transitions, cuts


def pose_at(progress: float, cells: tuple[Image.Image, ...], phases: list[str], cuts: set[tuple[int, int]]) -> tuple[Image.Image, str]:
    value = min(max(float(progress), 0.0), 1.0)
    if value <= DEFAULT_PROGRESS[0]:
        return cells[0], phases[0]
    for index, (start, end) in enumerate(zip(DEFAULT_PROGRESS, DEFAULT_PROGRESS[1:])):
        if value > end:
            continue
        amount = smoothstep((value - start) / max(end - start, 1e-6))
        if (index, index + 1) in cuts:
            pose = cells[index] if amount < 0.5 else cells[index + 1]
        else:
            pose = interpolate_pose(cells[index], cells[index + 1], amount)
        phase = phases[index] if amount < 0.5 else phases[index + 1]
        return pose, phase
    return cells[-1], phases[-1]


def fit_background(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGBA"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def paste_scene(frame: Image.Image, pose: Image.Image, key: str) -> None:
    profile = SCENE_PROFILES[key]
    target_height = round(512 * profile["scale"])
    target_width = round(448 * profile["scale"])
    scene = pose.resize((target_width, target_height), Image.Resampling.LANCZOS)
    left = round(WIDTH * profile["center_x"] - target_width / 2)
    top = GROUND_Y - target_height
    frame.alpha_composite(scene, (left, top))


def render_action(key: str, cells: tuple[Image.Image, ...], phases: list[str], background: Image.Image) -> tuple[list[Image.Image], list[str], dict[str, Any]]:
    transitions, cuts = transition_report(cells, phases)
    frames: list[Image.Image] = []
    frame_phases: list[str] = []
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / (FRAME_COUNT - 1)
        pose, phase = pose_at(progress, cells, phases, cuts)
        frame = background.copy()
        paste_scene(frame, pose, key)
        frames.append(frame.convert("RGB"))
        frame_phases.append(phase)
    return frames, frame_phases, {
        "transition_method_policy": "alpha-aware interpolation only for same-phase adjacent poses with safe alpha silhouette IoU; phase boundaries and stateful hold-result changes use midpoint hard pose cuts",
        "transitions": transitions,
        "pose_cut_count": len(cuts),
        "alpha_aware_transition_count": len(transitions) - len(cuts),
        "silhouette_iou_threshold": FLOW_MIN_SILHOUETTE_IOU,
    }


def write_video(path: Path, frames: list[Image.Image]) -> None:
    writer = imageio.get_writer(
        str(path), fps=FPS, codec="libx264", quality=8, macro_block_size=2,
        ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer returned no data for {path}")


def ffmpeg_probe(path: Path) -> dict[str, Any]:
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [executable, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    text = result.stderr
    video_line = next((line.strip() for line in text.splitlines() if "Video:" in line), "")
    pixel_format = "yuv420p" if "yuv420p" in video_line else ""
    codec_match = re.search(r"Video:\s*([^,\s]+)", video_line)
    codec = codec_match.group(1) if codec_match else ""
    return {
        "ffmpeg_decode_exit_code": result.returncode,
        "ffmpeg_video_stream": video_line,
        "codec": codec,
        "pixel_format": pixel_format,
        "codec_h264": codec.lower() in {"h264", "avc1"} or "h264" in video_line.lower(),
        "pixel_format_yuv420p": pixel_format == "yuv420p",
        "decode_ok": result.returncode == 0,
    }


def validate_video(path: Path) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
        first_frame = reader.get_data(0)
    finally:
        reader.close()
    probe = ffmpeg_probe(path)
    fps = float(metadata.get("fps") or 0.0)
    size = list(metadata.get("size") or ())
    report = {
        "path": str(path.resolve()),
        "resolution": size,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "imageio_codec": str(metadata.get("codec") or ""),
        "imageio_readable": first_frame is not None,
        "ffmpeg": probe,
        "metadata_verified": True,
    }
    if size != [WIDTH, HEIGHT] or frame_count != FRAME_COUNT or abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata for {path}: {report}")
    if not report["imageio_readable"] or not probe["decode_ok"] or not probe["codec_h264"] or not probe["pixel_format_yuv420p"]:
        raise RuntimeError(f"MP4 codec/readability validation failed for {path}: {report}")
    return report


def write_contact_sheet(path: Path, frames: list[Image.Image], phases: list[str], key: str) -> dict[str, Any]:
    tile_width, tile_height = 240, 120
    label_height, header_height = 25, 55
    columns, rows = 4, 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), "#edf1f4")
    draw = ImageDraw.Draw(sheet)
    title_font = font(18)
    label_font = font(13)
    draw.rectangle((0, 0, sheet.width, 30), fill="#263445")
    draw.text((10, 6), f"{CHARACTER} / {key} / rendered video contact", fill="#ffffff", font=title_font)
    draw.text((10, 35), "240 frames | 30 fps | 8.00 seconds | source status: prototype", fill="#3a4652", font=label_font)
    for sample_index in range(12):
        frame_index = min(round(sample_index * (len(frames) - 1) / 11), len(frames) - 1)
        x = (sample_index % columns) * tile_width
        y = header_height + (sample_index // columns) * (tile_height + label_height)
        draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill="#d6dfe7")
        draw.text((x + 6, y + 5), f"{frame_index / FPS:0.2f}s | {phases[frame_index]}", fill="#25313d", font=label_font)
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        sheet.paste(tile, (x, y + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [sheet.width, sheet.height], "exists": path.is_file(), "labels_included": True, "source": "actual_rendered_video_frames"}


def write_group_overview(path: Path, frames_by_key: dict[str, list[Image.Image]], phase_by_key: dict[str, list[str]]) -> dict[str, Any]:
    tile_width, tile_height = 240, 135
    label_height, header_height = 28, 50
    image = Image.new("RGB", (tile_width * len(ACTIONS), header_height + tile_height + label_height), "#e9eef2")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, 30), fill="#263445")
    draw.text((10, 6), "agent_01 prop interactions / rendered video overview", fill="#ffffff", font=font(18))
    draw.text((10, 35), "Hold/result samples from actual MP4 frames | all previews prototype", fill="#3a4652", font=font(13))
    for index, key in enumerate(ACTIONS):
        frames = frames_by_key[key]
        phases = phase_by_key[key]
        hold_indices = [i for i, phase in enumerate(phases) if phase == "hold"]
        frame_index = hold_indices[len(hold_indices) // 2] if hold_indices else round(len(frames) * 0.65)
        x = index * tile_width
        draw.rectangle((x, header_height, x + tile_width - 1, header_height + label_height - 1), fill="#d6dfe7")
        draw.text((x + 7, header_height + 6), f"{key} | {frame_index / FPS:0.2f}s hold", fill="#25313d", font=font(13))
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        image.paste(tile, (x, header_height + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [image.width, image.height], "exists": path.is_file(), "labels_included": True, "source": "actual_rendered_video_frames"}


def source_limitations(key: str, phase_json: dict[str, Any]) -> list[str]:
    limitations = {
        "open_chest": "Baked chest perspective and hand-to-lid contact still need runtime pivot alignment.",
        "unlock": "Baked door/lock/key composite should be redrawn against the runtime prop anchor.",
        "pick_up": "Baked floor patch should be replaced by the runtime floor layer before production use.",
        "lift": "Slab scale, grip geometry, and support collision need gameplay review.",
        "uncover": "Baked cloth folds and hand contact need cleanup before production use.",
    }
    return [limitations[key], "Motion-sheet edges and small generated details remain prototype quality.", f"Required conditions: {phase_json.get('required_conditions', {})}"]


def write_report(path: Path, rendered: list[dict[str, Any]], overview: dict[str, Any]) -> None:
    lines = [
        "# Round 4 Video Preview Report: agent_01 prop interactions",
        "",
        "Five H.264 prototype previews were rendered from the assigned 4x2 RGBA motion sheets. The camera is locked at 960x480 and all videos are 240 frames at 30 fps (8 seconds). MP4 frames contain no labels or debug overlays; labels are confined to derived contact sheets and the group overview.",
        "",
        "## Validation",
        "",
        f"- Videos rendered: {len(rendered)}/{len(ACTIONS)}.",
        "- Every MP4 passed imageio frame decoding and ffmpeg stream validation for 960x480, 30 fps, 240 frames, H.264, and yuv420p.",
        "- Every action has a labeled contact sheet sampled from its actual rendered frames.",
        f"- Group overview: `{overview['path']}`.",
        "- All assets retain `status=prototype` and `production_approved=false`.",
        "",
        "## Transition Methods",
        "",
        "Transition selection compares adjacent authored cell alpha silhouettes. Alpha-aware interpolation uses premultiplied RGB when silhouette IoU is safe; lower-overlap transitions use a midpoint hard pose cut to avoid ghosted composite props.",
        "",
        "| Key | Alpha-aware transitions | Pose cuts | Hold frames | Video | Contact |",
        "|---|---:|---:|---:|---|---|",
    ]
    for item in rendered:
        transition = item["quality_checks"]["interpolation"]
        lines.append(f"| `{item['key']}` | {transition['alpha_aware_transition_count']} | {transition['pose_cut_count']} | {item['phase_frame_counts']['hold']} | `{Path(item['video']['path']).name}` | `{Path(item['contact_sheet']['path']).name}` |")
    lines.extend(["", "## Action-Specific Limitations", ""])
    for item in rendered:
        lines.append(f"- `{item['key']}`: " + " ".join(item["limitations"]))
    lines.extend(["", "## Scope Guardrails", "", "- Only `assets/characters/motion_sheets/generated_round4/agent_01_prop_interactions` was read for authored action assets.", "- Only `output/video_previews/generated_round4/agent_01_prop_interactions` and `tools/next_actions/render_round4_01.py` were written.", "- Backend, Flutter, database code, and other groups were not modified."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_manifest_consistency(payload: dict[str, Any], output_dir: Path) -> None:
    if tuple(item["key"] for item in payload["assets"]) != ACTIONS:
        raise ValueError("Output manifest action order/key set is inconsistent")
    if payload["format"] != {
        "resolution": [WIDTH, HEIGHT], "fps": FPS, "duration_seconds": DURATION_SECONDS,
        "frame_count": FRAME_COUNT, "codec": "H.264/libx264", "pixel_format": "yuv420p",
    }:
        raise ValueError("Output manifest format is inconsistent")
    for item in payload["assets"]:
        if item["status"] != "prototype" or item["production_approved"] is not False:
            raise ValueError(f"Approval state changed for {item['key']}")
        for field in ("video", "contact_sheet"):
            if not Path(item[field]["path"]).is_file():
                raise FileNotFoundError(f"Missing output artifact for {item['key']}: {item[field]['path']}")
    if not Path(payload["group_video_overview"]["path"]).is_file():
        raise FileNotFoundError("Missing group video overview")
    if Path(payload["source_manifest"]).name != "group_manifest.json":
        raise ValueError("Unexpected source manifest")
    if output_dir.resolve() not in Path(payload["group_video_overview"]["path"]).resolve().parents:
        raise ValueError("Overview escaped assigned output folder")


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if input_dir != INPUT_DIR.resolve() or output_dir != OUTPUT_DIR.resolve():
        raise ValueError("This assigned renderer only accepts the agent_01 round4 input/output folders")
    group_manifest_path = input_dir / "group_manifest.json"
    if not group_manifest_path.is_file() or not BACKGROUND_PATH.is_file():
        raise FileNotFoundError("Assigned group manifest or stable background is missing")
    group_manifest = read_json(group_manifest_path)
    contracts = validate_source_contract(input_dir, group_manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    background = fit_background(BACKGROUND_PATH)
    rendered: list[dict[str, Any]] = []
    frames_by_key: dict[str, list[Image.Image]] = {}
    phases_by_key: dict[str, list[str]] = {}

    for key in ACTIONS:
        contract = contracts[key]
        cells = extract_cells(contract["sheet_path"])
        frames, frame_phases, interpolation = render_action(key, cells, contract["phases"], background)
        video_path = output_dir / f"male_01_{key}_generated_round4.mp4"
        contact_path = output_dir / f"male_01_{key}_generated_round4_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        contact_report = write_contact_sheet(contact_path, frames, frame_phases, key)
        phase_frame_counts = {phase: frame_phases.count(phase) for phase in PHASE_CONTRACT}
        item = {
            "key": key,
            "status": "prototype",
            "blocked": False,
            "production_approved": False,
            "source_asset": contract["asset"],
            "source_motion_sheet": str(contract["sheet_path"].resolve()),
            "source_phase_json": str(contract["phase_path"].resolve()),
            "source_contact_sheet": str(contract["source_contact_path"].resolve()),
            "phase_intent": contract["phase_json"]["phase_intent"],
            "timeline": [{"progress": progress, "cell": index + 1, "phase": contract["phases"][index]} for index, progress in enumerate(DEFAULT_PROGRESS)],
            "phase_frame_counts": phase_frame_counts,
            "video": video_report,
            "contact_sheet": contact_report,
            "limitations": source_limitations(key, contract["phase_json"]),
            "quality_checks": {
                "fixed_camera": True,
                "background": str(BACKGROUND_PATH.resolve()),
                "scene_profile": SCENE_PROFILES[key],
                "embedded_props_preserved": True,
                "debug_overlay_in_mp4": False,
                "labels_only_on_contact_sheet_and_overview": True,
                "interpolation": interpolation,
            },
        }
        rendered.append(item)
        frames_by_key[key] = frames
        phases_by_key[key] = frame_phases

    overview_path = output_dir / "group_video_overview.png"
    overview_report = write_group_overview(overview_path, frames_by_key, phases_by_key)
    payload = {
        "manifest_version": "round4-video-1.0",
        "render_status": "complete",
        "group": "agent_01_prop_interactions",
        "character": CHARACTER,
        "scope": list(ACTIONS),
        "status": "prototype",
        "production_approved": False,
        "source_manifest": str(group_manifest_path.resolve()),
        "format": {"resolution": [WIDTH, HEIGHT], "fps": FPS, "duration_seconds": DURATION_SECONDS, "frame_count": FRAME_COUNT, "codec": "H.264/libx264", "pixel_format": "yuv420p"},
        "timeline_contract": list(PHASE_CONTRACT),
        "background": str(BACKGROUND_PATH.resolve()),
        "group_video_overview": overview_report,
        "assets": rendered,
        "metadata_validation": {
            "all_videos_checked": all(item["video"]["metadata_verified"] for item in rendered),
            "all_imageio_readable": all(item["video"]["imageio_readable"] for item in rendered),
            "all_ffmpeg_decodable": all(item["video"]["ffmpeg"]["decode_ok"] for item in rendered),
            "all_h264": all(item["video"]["ffmpeg"]["codec_h264"] for item in rendered),
            "all_yuv420p": all(item["video"]["ffmpeg"]["pixel_format_yuv420p"] for item in rendered),
            "all_resolution_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in rendered),
            "all_fps_30": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in rendered),
            "all_frame_count_240": all(item["video"]["frame_count"] == FRAME_COUNT for item in rendered),
            "all_contacts_exist": all(item["contact_sheet"]["exists"] for item in rendered),
            "manifest_consistent": True,
            "asset_count": len(rendered),
        },
        "output_policy": {
            "assigned_group_only": True,
            "backend_modified": False,
            "flutter_modified": False,
            "database_modified": False,
            "other_groups_modified": False,
            "debug_overlays_in_mp4": False,
            "labels_only_on_derived_review_images": True,
        },
    }
    validate_manifest_consistency(payload, output_dir)
    manifest_out = output_dir / "group_video_manifest.json"
    manifest_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out = output_dir / "group_video_report.md"
    write_report(report_out, rendered, overview_report)
    print(json.dumps({"render_status": "complete", "videos": len(rendered), "contacts": len(rendered), "pose_cuts": {item["key"]: item["quality_checks"]["interpolation"]["pose_cut_count"] for item in rendered}, "manifest": str(manifest_out.resolve()), "report": str(report_out.resolve())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
