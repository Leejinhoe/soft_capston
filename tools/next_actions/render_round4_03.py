"""Render prototype video previews for the round-4 social-rescue motion sheets."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round4" / "agent_03_social_rescue"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round4" / "agent_03_social_rescue"
CANDIDATE_MANIFEST = ROOT / "tools" / "next_actions" / "asset_candidates_round4" / "agent_03_social_rescue.json"

CHARACTER = "male_01"
GROUP = "social_rescue"
ACTIONS = ("shake_hands", "beckon", "protect", "catch", "release")
PHASE_CONTRACT = ("prepare", "act", "hold", "recover")
WIDTH = 960
HEIGHT = 480
FPS = 30
FRAME_COUNT = 240
DURATION_SECONDS = 8.0
SHEET_COLUMNS = 4
SHEET_ROWS = 2
CELL_WIDTH = 448
CELL_HEIGHT = 512
SCENE_SCALE = 0.90
GROUND_ANCHOR_Y = 420
SILHOUETTE_IOU_THRESHOLD = 0.55

# These points preserve two prepare cells, two act cells, two hold cells, and
# two recovery cells, with a deliberately readable dwell over the hold pair.
TIMELINE_SECONDS = (0.00, 0.85, 1.70, 2.65, 3.55, 4.35, 5.40, 6.55, 8.00)
ACTION_LIMITATIONS = {
    "shake_hands": "Partner alignment, gaze, and exact shared-hand contact need a final scene pass.",
    "beckon": "The inward-call marks and partner approach path still need partner gaze and distance review.",
    "protect": "Threat travel, barrier contact, and depth ordering need engine collision and scene review.",
    "catch": "Ledge collision, moving-partner trajectory, and the grip safety margin need engine validation.",
    "release": "Restraint break timing, exit clearance, and free partner travel need engine validation.",
}
FORCED_POSE_CUTS = {
    # Moving partner/trajectory composites can leave a doubled partner during
    # interpolation even when the main character silhouettes overlap.
    "catch": {(index, index + 1) for index in range(7)},
    "protect": {(5, 6)},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve_input_path(value: str | Path, input_dir: Path) -> Path:
    raw = Path(str(value))
    candidates = (raw, ROOT / raw, input_dir / raw, input_dir / raw.name)
    root = input_dir.resolve()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if root not in resolved.parents:
                raise ValueError(f"Input asset escapes assigned group folder: {resolved}")
            return resolved
    raise FileNotFoundError(f"Could not resolve assigned input asset: {value}")


def load_sources(input_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    group_manifest_path = input_dir / "group_manifest.json"
    group_manifest = read_json(group_manifest_path)
    if group_manifest.get("manifest_version") != "4.0" or group_manifest.get("group") != GROUP:
        raise ValueError("Expected social_rescue round-4 group manifest")
    assets = group_manifest.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Group manifest has no assets list")
    records = {str(entry.get("key")): entry for entry in assets if isinstance(entry, dict)}
    if tuple(records) != ACTIONS:
        raise ValueError(f"Expected exactly {ACTIONS} in group manifest, got {tuple(records)}")

    candidate_manifest = read_json(CANDIDATE_MANIFEST)
    candidates = candidate_manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Candidate manifest has no candidates list")
    candidate_records = {str(entry.get("key")): entry for entry in candidates if isinstance(entry, dict)}
    if set(candidate_records) != set(ACTIONS):
        raise ValueError("Candidate contract does not cover exactly the assigned keys")

    phase_records: dict[str, dict[str, Any]] = {}
    for action in ACTIONS:
        entry = records[action]
        if entry.get("status") != "prototype" or bool(entry.get("blocked", False)):
            raise ValueError(f"Unexpected source status for {action}")
        paths = entry.get("paths")
        if not isinstance(paths, dict):
            raise ValueError(f"Missing paths for {action}")
        phase_path = resolve_input_path(paths.get("phases", ""), input_dir)
        phase = read_json(phase_path)
        if phase.get("word") != action or phase.get("character") != CHARACTER:
            raise ValueError(f"Phase JSON identity mismatch for {action}")
        intents = phase.get("phase_intent")
        if not isinstance(intents, list) or len(intents) != 8:
            raise ValueError(f"Expected eight phase intents for {action}")
        phase_names = tuple(str(item.get("phase")) for item in intents if isinstance(item, dict))
        expected = ("prepare", "prepare", "act", "act", "hold", "hold", "recover", "recover")
        if phase_names != expected:
            raise ValueError(f"Phase JSON cell contract mismatch for {action}: {phase_names}")
        contract = candidate_records[action].get("four_phase_contract")
        if not isinstance(contract, dict) or tuple(contract) != PHASE_CONTRACT:
            raise ValueError(f"Candidate four-phase contract mismatch for {action}")
        phase_records[action] = phase
    return group_manifest, candidate_manifest, phase_records


def extract_cells(sheet_path: Path) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
        if sheet.size != (1792, 1024) or sheet.mode != "RGBA":
            raise ValueError(f"Expected 1792x1024 RGBA motion sheet: {sheet_path}")
        cells: list[Image.Image] = []
        for index in range(8):
            column = index % SHEET_COLUMNS
            row = index // SHEET_COLUMNS
            cell = sheet.crop((column * CELL_WIDTH, row * CELL_HEIGHT,
                               (column + 1) * CELL_WIDTH, (row + 1) * CELL_HEIGHT))
            if cell.getchannel("A").getbbox() is None:
                raise ValueError(f"Empty alpha cell {index + 1}: {sheet_path}")
            cells.append(cell)
        return tuple(cells)


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    first_mask = np.asarray(first.getchannel("A")) >= 64
    second_mask = np.asarray(second.getchannel("A")) >= 64
    union = np.logical_or(first_mask, second_mask).sum()
    return float(np.logical_and(first_mask, second_mask).sum() / union) if union else 0.0


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def alpha_aware_interpolate(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    amount = smoothstep(amount)
    first_array = np.asarray(first, dtype=np.float32) / 255.0
    second_array = np.asarray(second, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    rgb = first_array[..., :3] * first_alpha * (1.0 - amount)
    rgb += second_array[..., :3] * second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def interpolation_plan(cells: tuple[Image.Image, ...], action: str) -> dict[str, Any]:
    transitions = []
    pose_cuts: set[tuple[int, int]] = set()
    forced_cuts = FORCED_POSE_CUTS.get(action, set())
    for index, (first, second) in enumerate(zip(cells, cells[1:])):
        overlap = alpha_iou(first, second)
        pair = (index, index + 1)
        if pair in forced_cuts:
            method = "hard_pose_cut_scene_composite"
        else:
            method = "alpha_aware_interpolation" if overlap >= SILHOUETTE_IOU_THRESHOLD else "hard_pose_cut"
        if method != "alpha_aware_interpolation":
            pose_cuts.add((index, index + 1))
        transitions.append({
            "from_cell": index + 1,
            "to_cell": index + 2,
            "silhouette_iou": round(overlap, 4),
            "method": method,
        })
    return {
        "silhouette_iou_threshold": SILHOUETTE_IOU_THRESHOLD,
        "transitions": transitions,
        "pose_cuts": [list(pair) for pair in sorted(pose_cuts)],
        "pose_cut_count": len(pose_cuts),
    }


def timeline_for(phase_json: dict[str, Any]) -> tuple[tuple[float, int, str], ...]:
    intents = phase_json["phase_intent"]
    phases = tuple(str(item["phase"]) for item in intents)
    return tuple((TIMELINE_SECONDS[index], index, phases[index]) for index in range(8)) + ((8.0, 7, phases[7]),)


def pose_at(
    seconds: float,
    timeline: tuple[tuple[float, int, str], ...],
    cells: tuple[Image.Image, ...],
    pose_cuts: set[tuple[int, int]],
) -> tuple[Image.Image, str]:
    value = min(max(float(seconds), 0.0), DURATION_SECONDS)
    segment = len(timeline) - 2
    for index in range(len(timeline) - 1):
        if value < timeline[index + 1][0]:
            segment = index
            break
    start, first_index, phase = timeline[segment]
    end, second_index, _ = timeline[segment + 1]
    if first_index == second_index or end <= start:
        return cells[first_index], phase
    amount = (value - start) / (end - start)
    if (first_index, second_index) in pose_cuts:
        pose = cells[first_index] if amount < 0.5 else cells[second_index]
    else:
        pose = alpha_aware_interpolate(cells[first_index], cells[second_index], amount)
    return pose, phase


def build_background() -> Image.Image:
    background = Image.new("RGBA", (WIDTH, HEIGHT), (193, 210, 218, 255))
    draw = ImageDraw.Draw(background, "RGBA")
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        color = (193 - round(ratio * 21), 210 - round(ratio * 16), 218 - round(ratio * 9), 255)
        draw.line((0, y, WIDTH, y), fill=color)
    draw.polygon([(0, 318), (145, 274), (292, 310), (452, 252), (640, 304),
                  (786, 266), (960, 304), (960, 420), (0, 420)], fill=(106, 134, 128, 110))
    draw.polygon([(0, 369), (180, 334), (346, 362), (530, 326), (726, 360),
                  (862, 330), (960, 354), (960, HEIGHT), (0, HEIGHT)], fill=(91, 116, 104, 180))
    draw.rectangle((0, GROUND_ANCHOR_Y, WIDTH, HEIGHT), fill=(75, 96, 83, 210))
    draw.line((0, GROUND_ANCHOR_Y, WIDTH, GROUND_ANCHOR_Y), fill=(221, 211, 177, 170), width=3)
    for x in range(-20, WIDTH + 40, 58):
        draw.line((x, GROUND_ANCHOR_Y + 10, x + 18, GROUND_ANCHOR_Y + 22), fill=(182, 176, 146, 80), width=2)
    background = background.filter(ImageFilter.GaussianBlur(0.35))
    return background


def paste_pose(frame: Image.Image, pose: Image.Image, *, ground_ref: int) -> None:
    target_size = (round(CELL_WIDTH * SCENE_SCALE), round(CELL_HEIGHT * SCENE_SCALE))
    scaled = pose.resize(target_size, Image.Resampling.LANCZOS)
    x = round((WIDTH - scaled.width) / 2)
    y = round(GROUND_ANCHOR_Y - ground_ref * SCENE_SCALE)
    frame.alpha_composite(scaled, (x, y))


def render_frames(
    cells: tuple[Image.Image, ...],
    phase_json: dict[str, Any],
    plan: dict[str, Any],
    background: Image.Image,
) -> Iterable[Image.Image]:
    timeline = timeline_for(phase_json)
    pose_cuts = {tuple(pair) for pair in plan["pose_cuts"]}
    ground_refs = [cell.getchannel("A").getbbox()[3] for cell in cells]
    ground_ref = max(ground_refs)
    for frame_index in range(FRAME_COUNT):
        pose, _phase = pose_at(frame_index / FPS, timeline, cells, pose_cuts)
        frame = background.copy()
        paste_pose(frame, pose, ground_ref=ground_ref)
        yield frame.convert("RGB")


def font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def write_video(path: Path, frames: Iterable[Image.Image]) -> None:
    writer = imageio.get_writer(
        str(path), fps=FPS, codec="libx264", quality=8, macro_block_size=1,
        ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer returned no data: {path}")


def ffmpeg_stream_probe(path: Path) -> dict[str, Any]:
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    completed = subprocess.run(
        [executable, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    probe_text = f"{completed.stdout}\n{completed.stderr}"
    codec_match = re.search(r"Video:\s+([^,\s]+)", probe_text)
    pixel_match = re.search(r"\b(yuv\d+p(?:\d+)?)\b", probe_text)
    codec = codec_match.group(1) if codec_match else "unknown"
    pixel_format = pixel_match.group(1) if pixel_match else "unknown"
    if completed.returncode not in (0, 1) or "h264" not in probe_text.lower() or pixel_format != "yuv420p":
        raise RuntimeError(f"ffmpeg stream probe failed for {path.name}: {probe_text[-1200:]}")
    return {"codec": codec, "pixel_format": pixel_format, "probe_verified": True}


def validate_video(path: Path) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        actual_count = int(reader.count_frames())
        first_frame = reader.get_data(0)
    finally:
        reader.close()
    size = list(metadata.get("size") or ())
    fps = float(metadata.get("fps") or 0.0)
    if size != [WIDTH, HEIGHT] or actual_count != FRAME_COUNT or abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata for {path.name}: {metadata}, count={actual_count}")
    stream = ffmpeg_stream_probe(path)
    if first_frame is None:
        raise RuntimeError(f"First frame is unreadable: {path}")
    return {
        "path": str(path.resolve()),
        "resolution": size,
        "fps": fps,
        "frame_count": actual_count,
        "duration_seconds": round(actual_count / fps, 3),
        "codec": stream["codec"],
        "pixel_format": stream["pixel_format"],
        "imageio_readable": True,
        "metadata_verified": True,
        "h264_verified": True,
        "yuv420p_verified": True,
    }


def phase_counts_from_timeline(phase_json: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    timeline = timeline_for(phase_json)
    phases: list[str] = []
    for frame_index in range(FRAME_COUNT):
        _pose, phase = pose_at(frame_index / FPS, timeline, tuple(Image.new("RGBA", (1, 1)) for _ in range(8)), set())
        phases.append(phase)
    return {phase: phases.count(phase) for phase in PHASE_CONTRACT}, phases


def write_contact_sheet(video_path: Path, output_path: Path, action: str, phase_json: dict[str, Any]) -> dict[str, Any]:
    reader = imageio.get_reader(str(video_path))
    try:
        count = int(reader.count_frames())
        tile_width, tile_height = 240, 120
        label_height, header_height = 24, 46
        columns, samples = 4, 12
        rows = math.ceil(samples / columns)
        sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), (241, 244, 246))
        draw = ImageDraw.Draw(sheet)
        typeface = font()
        draw.rectangle((0, 0, sheet.width, header_height), fill=(30, 43, 58))
        draw.text((10, 7), f"{CHARACTER} {action} | rendered MP4 contact", fill="white", font=typeface)
        draw.text((10, 27), "prepare / act / hold / recover", fill=(208, 219, 227), font=font(13))
        timeline = timeline_for(phase_json)
        for sample_index in range(samples):
            frame_index = round(sample_index * (count - 1) / max(1, samples - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame = frame.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            _pose, phase = pose_at(frame_index / FPS, timeline, tuple(Image.new("RGBA", (1, 1)) for _ in range(8)), set())
            x = (sample_index % columns) * tile_width
            y = header_height + (sample_index // columns) * (tile_height + label_height)
            draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(216, 225, 231))
            draw.text((x + 7, y + 5), f"{frame_index / FPS:0.2f}s | {phase}", fill=(28, 39, 50), font=font(14))
            sheet.paste(frame, (x, y + label_height))
    finally:
        reader.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Contact sheet was not written: {output_path}")
    return {"path": str(output_path.resolve()), "resolution": list(sheet.size), "sample_count": samples, "labels_included": True, "from_rendered_video": True}


def write_group_overview(output_dir: Path, video_paths: dict[str, Path], phase_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tile_width, tile_height = 192, 96
    label_height, header_height = 22, 32
    sheet = Image.new("RGB", (len(ACTIONS) * tile_width, header_height + 4 * (tile_height + label_height)), (240, 243, 245))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, sheet.width, header_height), fill=(30, 43, 58))
    draw.text((10, 8), "agent_03_social_rescue | rendered round-4 video overview", fill="white", font=font(15))
    for column, action in enumerate(ACTIONS):
        reader = imageio.get_reader(str(video_paths[action]))
        try:
            for row, frame_index in enumerate((0, 51, 120, 204)):
                frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB").resize((tile_width, tile_height), Image.Resampling.LANCZOS)
                _pose, phase = pose_at(frame_index / FPS, timeline_for(phase_records[action]), tuple(Image.new("RGBA", (1, 1)) for _ in range(8)), set())
                x = column * tile_width
                y = header_height + row * (tile_height + label_height)
                draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(216, 225, 231))
                draw.text((x + 5, y + 4), f"{action} | {frame_index / FPS:0.2f}s {phase}", fill=(28, 39, 50), font=font(11))
                sheet.paste(frame, (x, y + label_height))
        finally:
            reader.close()
    path = output_dir / "group_video_overview.png"
    sheet.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": list(sheet.size), "samples_per_key": 4, "from_rendered_videos": True}


def render_action(
    action: str,
    source_entry: dict[str, Any],
    phase_json: dict[str, Any],
    input_dir: Path,
    output_dir: Path,
    background: Image.Image,
) -> tuple[dict[str, Any], Path]:
    sheet_path = resolve_input_path(source_entry["paths"]["motion_sheet"], input_dir)
    cells = extract_cells(sheet_path)
    plan = interpolation_plan(cells, action)
    video_path = output_dir / f"{CHARACTER}_{action}_round4.mp4"
    contact_path = output_dir / f"{CHARACTER}_{action}_round4_contact.png"
    write_video(video_path, render_frames(cells, phase_json, plan, background))
    video_report = validate_video(video_path)
    contact_report = write_contact_sheet(video_path, contact_path, action, phase_json)
    phase_counts, _ = phase_counts_from_timeline(phase_json)
    timeline = timeline_for(phase_json)
    result = {
        "key": action,
        "character": CHARACTER,
        "status": "prototype",
        "production_approved": False,
        "source_manifest_entry": source_entry,
        "source_motion_sheet": str(sheet_path.resolve()),
        "source_phase_json": str(resolve_input_path(source_entry["paths"]["phases"], input_dir).resolve()),
        "timeline": [{"time_seconds": point[0], "cell_1_based": point[1] + 1, "phase": point[2]} for point in timeline[:8]],
        "phase_frame_counts": phase_counts,
        "transition_methods": plan["transitions"],
        "pose_cut_count": plan["pose_cut_count"],
        "video": video_report,
        "contact_sheet": contact_report,
        "limitations": ACTION_LIMITATIONS[action],
        "quality_checks": {
            "motion_sheet_unmodified": True,
            "embedded_partner_props_targets_preserved": True,
            "fixed_camera": True,
            "background_behind_authored_scene": True,
            "debug_overlays_in_mp4": False,
            "phase_text_in_mp4": False,
            "labels_only_in_contact_artifacts": True,
            "timeline_contract": list(PHASE_CONTRACT),
        },
    }
    return result, video_path


def write_report(path: Path, results: list[dict[str, Any]], overview: dict[str, Any]) -> None:
    total_cuts = sum(int(item["pose_cut_count"]) for item in results)
    lines = [
        "# Round 4 Social Rescue Video Previews",
        "",
        "Rendered five prototype MP4 previews from the assigned 4x2 RGBA motion sheets.",
        "",
        "## Delivery",
        "",
        f"- Videos: {len(results)}; contact sheets: {len(results)}; total frames: {len(results) * FRAME_COUNT}.",
        f"- Format: {WIDTH}x{HEIGHT}, {FPS} fps, {FRAME_COUNT} frames, H.264, yuv420p.",
        "- Timeline: prepare -> act -> hold -> recover, with two authored cells per phase and a readable hold dwell.",
        f"- Transition policy: alpha-aware interpolation at silhouette IoU >= {SILHOUETTE_IOU_THRESHOLD}; hard cuts below that threshold.",
        f"- Pose cuts: {total_cuts} total across the five videos.",
        "- All source and output statuses remain prototype; production_approved is false for every key.",
        "",
        "## Action Notes",
        "",
    ]
    for item in results:
        lines.append(f"- `{item['key']}`: {item['pose_cut_count']} pose cuts. {item['limitations']}")
    lines.extend([
        "",
        "## Validation",
        "",
        "Every MP4 was read with imageio/ffmpeg and checked for resolution, 30 fps, 240 frames, H.264, and yuv420p. Each contact sheet was generated by sampling its rendered MP4, and the group overview was sampled from the rendered MP4s.",
        "",
        f"Group overview: `{overview['path']}`",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_manifest(manifest: dict[str, Any], output_dir: Path) -> None:
    if manifest.get("render_status") != "complete" or manifest.get("status_policy") != "prototype_only":
        raise ValueError("Output manifest status policy is inconsistent")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or tuple(item.get("key") for item in assets) != ACTIONS:
        raise ValueError("Output manifest key set/order is inconsistent")
    for item in assets:
        if item.get("status") != "prototype" or item.get("production_approved") is not False:
            raise ValueError(f"Output approval policy mismatch for {item.get('key')}")
        video = item.get("video", {})
        if video.get("resolution") != [WIDTH, HEIGHT] or video.get("frame_count") != FRAME_COUNT:
            raise ValueError(f"Output video metadata mismatch for {item.get('key')}")
        if not item.get("contact_sheet", {}).get("labels_included"):
            raise ValueError(f"Missing contact validation for {item.get('key')}")
        if not (output_dir / Path(str(video.get("path", ""))).name).is_file():
            raise ValueError(f"Manifest video missing for {item.get('key')}")


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if input_dir != INPUT_DIR.resolve() or output_dir != OUTPUT_DIR.resolve():
        raise ValueError("This renderer is scoped to the assigned agent_03_social_rescue folders.")
    group_manifest, candidate_manifest, phase_records = load_sources(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    background = build_background()
    results: list[dict[str, Any]] = []
    video_paths: dict[str, Path] = {}
    for action in ACTIONS:
        result, video_path = render_action(action, next(entry for entry in group_manifest["assets"] if entry["key"] == action), phase_records[action], input_dir, output_dir, background)
        results.append(result)
        video_paths[action] = video_path
    overview = write_group_overview(output_dir, video_paths, phase_records)
    manifest = {
        "manifest_version": "round4-video-1.0",
        "render_status": "complete",
        "group": GROUP,
        "character": CHARACTER,
        "scope": list(ACTIONS),
        "source_group_manifest": str((input_dir / "group_manifest.json").resolve()),
        "candidate_contract_manifest": str(CANDIDATE_MANIFEST.resolve()),
        "delivery": {
            "resolution": [WIDTH, HEIGHT],
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT,
            "codec": "H.264/libx264",
            "pixel_format": "yuv420p",
            "timeline": list(PHASE_CONTRACT),
            "camera": "fixed",
            "background": "neutral fantasy ground-and-hills plate behind the authored composites",
            "ground_anchor_y": GROUND_ANCHOR_Y,
        },
        "assets": results,
        "group_video_overview": overview,
        "metadata_validation": {
            "asset_count": len(results),
            "video_count": len(video_paths),
            "contact_sheet_count": sum(1 for item in results if item["contact_sheet"]["from_rendered_video"]),
            "all_imageio_readable": all(item["video"]["imageio_readable"] for item in results),
            "all_h264": all(item["video"]["h264_verified"] for item in results),
            "all_yuv420p": all(item["video"]["yuv420p_verified"] for item in results),
            "all_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in results),
            "all_30fps": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in results),
            "all_240_frames": all(item["video"]["frame_count"] == FRAME_COUNT for item in results),
            "all_contacts_exist": all(Path(item["contact_sheet"]["path"]).is_file() for item in results),
        },
        "status_policy": "prototype_only",
        "output_policy": {
            "only_assigned_group_written": True,
            "motion_sheets_modified": False,
            "backend_flutter_database_modified": False,
            "other_groups_modified": False,
            "debug_overlays_in_mp4": False,
            "production_approved_for_all": False,
        },
        "generated_files": [
            *(f"{CHARACTER}_{action}_round4.mp4" for action in ACTIONS),
            *(f"{CHARACTER}_{action}_round4_contact.png" for action in ACTIONS),
            "group_video_manifest.json",
            "group_video_report.md",
            "group_video_overview.png",
        ],
    }
    manifest_path = output_dir / "group_video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    validate_manifest(manifest, output_dir)
    write_report(output_dir / "group_video_report.md", results, overview)
    print(json.dumps({"render_status": "complete", "videos": len(results), "contacts": len(results), "pose_cuts": sum(item["pose_cut_count"] for item in results), "manifest": str(manifest_path.resolve())}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
