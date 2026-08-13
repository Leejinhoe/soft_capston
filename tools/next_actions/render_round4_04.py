"""Render the five generated_round4 reaction/observation preview videos.

The source cells are scene-bound RGBA composites, so the renderer keeps each
448x512 cell intact and places the whole scene on a fixed fantasy background.
Phase names and source paths are read from the group and per-key manifests.
Review labels are written only to PNG contact sheets and the group overview;
the MP4 frames contain scene pixels only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round4" / "agent_04_reactions_observation"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round4" / "agent_04_reactions_observation"
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png"

CHARACTER = "male_01"
GROUP = "agent_04_reactions_observation"
KEYS = ("cower", "hesitate", "eavesdrop", "spot", "gasp")
WIDTH = 960
HEIGHT = 480
FPS = 30
FRAME_COUNT = 240
DURATION_SECONDS = 8.0
GRID_COLUMNS = 4
GRID_ROWS = 2
PHASE_CONTRACT = ("prepare", "act", "hold", "recover")

# The long hold interval is intentional: the authored target, barrier, or
# partner cue needs to remain readable in a review-length preview.
TIMELINE_POINTS: dict[str, tuple[float, ...]] = {
    "cower": (0.00, 0.13, 0.28, 0.41, 0.59, 0.72, 0.87, 1.00),
    "hesitate": (0.00, 0.14, 0.29, 0.42, 0.60, 0.74, 0.88, 1.00),
    "eavesdrop": (0.00, 0.14, 0.29, 0.42, 0.60, 0.74, 0.88, 1.00),
    "spot": (0.00, 0.14, 0.29, 0.42, 0.59, 0.73, 0.88, 1.00),
    "gasp": (0.00, 0.14, 0.29, 0.42, 0.59, 0.73, 0.88, 1.00),
}

# The reveal is embedded in the authored scene composite. Blending those
# pairs creates a duplicated leaf/key or star, so use a readable pose cut.
FORCED_POSE_CUTS: dict[str, set[tuple[int, int]]] = {
    "cower": set(),
    "hesitate": set(),
    "eavesdrop": set(),
    "spot": {(1, 2), (2, 3)},
    "gasp": {(1, 2)},
}

# Scale is applied to the entire cell, not just its alpha bounding box. This
# preserves the authored relationship among character, prop, target, partner,
# barrier, and terrain while keeping the source scene inside the camera.
SCENE_PLACEMENT: dict[str, dict[str, float]] = {
    "cower": {"scale": 0.92, "center_x": 480.0, "cell_bottom": 490.0},
    "hesitate": {"scale": 0.92, "center_x": 480.0, "cell_bottom": 490.0},
    "eavesdrop": {"scale": 0.92, "center_x": 480.0, "cell_bottom": 490.0},
    "spot": {"scale": 0.92, "center_x": 480.0, "cell_bottom": 490.0},
    "gasp": {"scale": 0.98, "center_x": 480.0, "cell_bottom": 490.0},
}

SILHOUETTE_IOU_THRESHOLD = 0.40

LIMITATIONS: dict[str, list[str]] = {
    "cower": [
        "Scene-bound prototype: the dragon threat and stone floor remain embedded in every pose.",
        "The dragon head is cropped at the upper-right edge and is not a reusable separate asset.",
    ],
    "hesitate": [
        "Scene-bound prototype: the closed dark door, brass handle, and floor remain embedded.",
        "The action intentionally stops short of contact and does not change door state.",
    ],
    "eavesdrop": [
        "The wall/doorframe, speaking partner, and speech-wave cue are required for the action to read.",
        "Audio timing is not represented; this is a visual preview only.",
    ],
    "spot": [
        "The leaf-to-key reveal is embedded in the scene composite, not a separate target layer.",
        "The key remains on the ground and untouched for the later pick_up action.",
    ],
    "gasp": [
        "The face read depends on the open box and glowing star remaining visible together.",
        "The star reveal is embedded in the scene composite rather than a reusable target layer.",
    ],
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
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def resolve_under(path_value: str | Path, root: Path) -> Path:
    raw = Path(str(path_value))
    candidates = (raw, root / raw, root / raw.name)
    root_resolved = root.resolve()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved != root_resolved and root_resolved not in resolved.parents:
                raise ValueError(f"Refusing source outside assigned input folder: {resolved}")
            return resolved
    raise FileNotFoundError(f"Could not resolve source path {path_value!r} under {root}")


def load_inputs(input_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    group_path = input_dir / "group_manifest.json"
    group_manifest = read_json(group_path)
    if group_manifest.get("format", {}).get("grid") != "4x2 row-major":
        raise ValueError("Assigned group manifest does not declare a 4x2 row-major grid")
    if group_manifest.get("format", {}).get("sheet_size") != [1792, 1024]:
        raise ValueError("Assigned group manifest does not declare 1792x1024 sheets")

    records = group_manifest.get("assets")
    if not isinstance(records, list):
        raise ValueError("Assigned group manifest has no assets list")
    by_key = {str(record.get("key")): record for record in records if isinstance(record, dict)}
    if set(by_key) != set(KEYS):
        raise ValueError(f"Assigned group manifest keys are {sorted(by_key)}, expected {list(KEYS)}")

    loaded: dict[str, dict[str, Any]] = {}
    for key in KEYS:
        asset = by_key[key]
        if asset.get("status") != "prototype" or bool(asset.get("blocked")):
            raise ValueError(f"{key}: source status/blocked state is not the expected prototype/unblocked contract")
        paths = asset.get("paths") or {}
        sheet_path = resolve_under(paths.get("motion_sheet"), input_dir)
        phase_path = resolve_under(paths.get("phases"), input_dir)
        phase_json = read_json(phase_path)
        if phase_json.get("key") != key or phase_json.get("status") != "prototype" or bool(phase_json.get("blocked")):
            raise ValueError(f"{key}: phase JSON does not match the expected prototype contract")
        phase_intent = phase_json.get("phase_intent")
        if not isinstance(phase_intent, list) or len(phase_intent) != 8:
            raise ValueError(f"{key}: expected eight phase_intent entries")
        phases = [str(item.get("phase", "")) for item in phase_intent]
        if phases != ["prepare", "prepare", "act", "act", "hold", "hold", "recover", "recover"]:
            raise ValueError(f"{key}: phase JSON does not expose the required four-phase contract: {phases}")
        loaded[key] = {
            "asset": asset,
            "phase_json": phase_json,
            "sheet_path": sheet_path,
            "phase_path": phase_path,
            "phase_intent": phase_intent,
        }
    return group_manifest, loaded


def extract_cells(sheet_path: Path) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
        if sheet.size != (1792, 1024):
            raise ValueError(f"{sheet_path.name}: expected 1792x1024, got {sheet.size}")
        cells: list[Image.Image] = []
        for index in range(GRID_COLUMNS * GRID_ROWS):
            column = index % GRID_COLUMNS
            row = index // GRID_COLUMNS
            left = column * 448
            top = row * 512
            cell = sheet.crop((left, top, left + 448, top + 512))
            if cell.getchannel("A").getbbox() is None:
                raise ValueError(f"Empty alpha cell {index + 1} in {sheet_path}")
            cells.append(cell)
        return tuple(cells)


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def alpha_iou(first: Image.Image, second: Image.Image) -> float:
    first_mask = np.asarray(first.getchannel("A"), dtype=np.uint8) >= 64
    second_mask = np.asarray(second.getchannel("A"), dtype=np.uint8) >= 64
    union = np.logical_or(first_mask, second_mask).sum()
    return float(np.logical_and(first_mask, second_mask).sum() / union) if union else 0.0


def interpolate_pose(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    t = smoothstep(amount)
    first_array = np.asarray(first, dtype=np.float32) / 255.0
    second_array = np.asarray(second, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    alpha = first_alpha * (1.0 - t) + second_alpha * t
    rgb = first_array[..., :3] * first_alpha * (1.0 - t)
    rgb += second_array[..., :3] * second_alpha * t
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def timeline_for(key: str, phase_intent: list[dict[str, Any]]) -> tuple[tuple[float, int, str], ...]:
    points = TIMELINE_POINTS[key]
    if len(points) != len(phase_intent):
        raise ValueError(f"{key}: timing points do not match phase JSON")
    return tuple((point, index, str(item["phase"])) for index, (point, item) in enumerate(zip(points, phase_intent)))


def pose_at(
    timeline: tuple[tuple[float, int, str], ...],
    progress: float,
    cells: tuple[Image.Image, ...],
    cut_pairs: set[tuple[int, int]],
) -> tuple[Image.Image, str]:
    value = min(max(float(progress), 0.0), 1.0)
    if value <= timeline[0][0]:
        return cells[timeline[0][1]], timeline[0][2]
    for first, second in zip(timeline, timeline[1:]):
        start, first_cell, first_phase = first
        end, second_cell, second_phase = second
        if value > end:
            continue
        amount = smoothstep((value - start) / max(end - start, 1e-6))
        if (first_cell, second_cell) in cut_pairs:
            pose = cells[first_cell] if amount < 0.5 else cells[second_cell]
        else:
            pose = interpolate_pose(cells[first_cell], cells[second_cell], amount)
        return pose, first_phase if amount < 0.5 else second_phase
    return cells[timeline[-1][1]], timeline[-1][2]


def fit_background(path: Path) -> Image.Image:
    with Image.open(path) as source:
        background = ImageOps.fit(
            source.convert("RGBA"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
    # A restrained darkening keeps the authored scene composite and its small
    # target/partner cues legible without adding any review graphics.
    return ImageEnhance.Brightness(background).enhance(0.68)


def place_scene(frame: Image.Image, cell: Image.Image, placement: dict[str, float]) -> None:
    scale = placement["scale"]
    width = round(cell.width * scale)
    height = round(cell.height * scale)
    scene = cell.resize((width, height), Image.Resampling.LANCZOS)
    left = round(placement["center_x"] - width / 2.0)
    top = round(placement["cell_bottom"] - height)
    frame.alpha_composite(scene, (left, top))


def transition_report(key: str, cells: tuple[Image.Image, ...]) -> tuple[list[dict[str, Any]], set[tuple[int, int]]]:
    forced = FORCED_POSE_CUTS[key]
    transitions: list[dict[str, Any]] = []
    cut_pairs: set[tuple[int, int]] = set()
    for index, (first, second) in enumerate(zip(cells, cells[1:])):
        pair = (index, index + 1)
        iou = alpha_iou(first, second)
        if pair in forced:
            method = "pose_cut"
            reason = "forced for embedded scene reveal"
            cut_pairs.add(pair)
        elif iou < SILHOUETTE_IOU_THRESHOLD:
            method = "pose_cut"
            reason = "silhouette overlap below safe interpolation threshold"
            cut_pairs.add(pair)
        else:
            method = "alpha_aware"
            reason = "silhouette overlap is safe for premultiplied alpha interpolation"
        transitions.append({
            "from_cell_1_based": index + 1,
            "to_cell_1_based": index + 2,
            "silhouette_iou": round(iou, 4),
            "method": method,
            "reason": reason,
        })
    return transitions, cut_pairs


def render_action(
    key: str,
    cells: tuple[Image.Image, ...],
    phase_intent: list[dict[str, Any]],
    background: Image.Image,
) -> tuple[list[Image.Image], list[str], dict[str, Any]]:
    timeline = timeline_for(key, phase_intent)
    transitions, cut_pairs = transition_report(key, cells)
    frames: list[Image.Image] = []
    phases: list[str] = []
    placement = SCENE_PLACEMENT[key]
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / max(FRAME_COUNT - 1, 1)
        pose, phase = pose_at(timeline, progress, cells, cut_pairs)
        frame = background.copy()
        place_scene(frame, pose, placement)
        frames.append(frame.convert("RGB"))
        phases.append(phase)
    counts = Counter(phases)
    return frames, phases, {
        "timeline_points": [round(item[0], 4) for item in timeline],
        "phase_by_cell_1_based": [item[2] for item in timeline],
        "frames_by_phase": {phase: counts.get(phase, 0) for phase in PHASE_CONTRACT},
        "transitions": transitions,
        "transition_method_counts": dict(Counter(item["method"] for item in transitions)),
        "pose_cut_count": len(cut_pairs),
        "pose_cut_pairs_0_based": [list(pair) for pair in sorted(cut_pairs)],
        "silhouette_iou_threshold": SILHOUETTE_IOU_THRESHOLD,
        "placement": placement,
    }


def font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def write_contact_sheet(path: Path, key: str, frames: list[Image.Image], phases: list[str]) -> dict[str, Any]:
    tile_width, tile_height = 240, 120
    label_height, header_height = 23, 78
    columns, rows = 4, 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), "#eef1f4")
    draw = ImageDraw.Draw(sheet)
    typeface = font()
    draw.rectangle((0, 0, sheet.width, 26), fill="#7b5a20")
    draw.text((8, 6), f"{CHARACTER} {key} | prototype | review only", fill="white", font=typeface)
    draw.text((8, 35), "8.00s | 240 frames | 30fps | labels are contact-sheet only", fill="#26313b", font=font(14))
    limitation = LIMITATIONS[key][0]
    wrapped = textwrap.wrap(limitation, width=112)[:2]
    for index, line in enumerate(wrapped):
        draw.text((8, 51 + index * 13), line, fill="#26313b", font=font(12))
    for sample_index in range(12):
        frame_index = min(round(sample_index * (len(frames) - 1) / 11), len(frames) - 1)
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = (sample_index % columns) * tile_width
        y = header_height + (sample_index // columns) * (tile_height + label_height)
        draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill="#d5dce2")
        draw.text((x + 7, y + 4), f"{frame_index / FPS:0.2f}s | {phases[frame_index]}", fill="#26313b", font=font(14))
        sheet.paste(tile, (x, y + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [sheet.width, sheet.height], "labels_included": True, "exists": path.is_file()}


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


def ffmpeg_stream_info(path: Path) -> dict[str, Any]:
    try:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
        completed = subprocess.run(
            [executable, "-hide_banner", "-i", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        output = completed.stdout + "\n" + completed.stderr
        match = re.search(r"Video:\s*([^,\s]+).*?\b(yuv420p)\b.*?(\d{2,5})x(\d{2,5})", output, re.IGNORECASE | re.DOTALL)
        if match:
            return {"codec": match.group(1), "pixel_format": match.group(2), "width": int(match.group(3)), "height": int(match.group(4)), "probe_available": True}
    except (OSError, ImportError):
        pass
    return {"codec": "", "pixel_format": "", "width": 0, "height": 0, "probe_available": False}


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
    codec = str(metadata.get("codec") or "")
    probe = ffmpeg_stream_info(path)
    codec_text = f"{codec} {probe.get('codec', '')}".lower()
    resolution = [probe["width"], probe["height"]] if probe["probe_available"] else size
    pixel_format = probe.get("pixel_format") or "yuv420p (writer setting)"
    report = {
        "path": str(path.resolve()),
        "resolution": resolution,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / fps, 3) if fps else 0.0,
        "codec": probe.get("codec") or codec or "h264",
        "pixel_format": pixel_format,
        "codec_readable": first_frame is not None,
        "metadata_verified": True,
        "ffmpeg_probe": probe,
    }
    if resolution != [WIDTH, HEIGHT] or size != [WIDTH, HEIGHT] or frame_count != FRAME_COUNT or abs(fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata for {path}: {report}")
    if not any(token in codec_text for token in ("h264", "avc1", "264")):
        raise RuntimeError(f"Unexpected MP4 codec for {path}: {report}")
    if probe["probe_available"] and probe["pixel_format"].lower() != "yuv420p":
        raise RuntimeError(f"Unexpected pixel format for {path}: {report}")
    return report


def write_group_overview(path: Path, rendered: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tile_width, tile_height = 220, 110
    label_height, row_label_width = 24, 116
    columns = 4
    header_height = 42
    row_height = label_height + tile_height
    overview = Image.new("RGB", (row_label_width + columns * tile_width, header_height + len(KEYS) * row_height), "#edf1f4")
    draw = ImageDraw.Draw(overview)
    draw.rectangle((0, 0, overview.width, header_height), fill="#23313d")
    draw.text((10, 7), "agent_04_reactions_observation | rendered prototype previews", fill="white", font=font(15))
    draw.text((10, 24), "Actual MP4 frames | prepare / act / hold / recover", fill="#d6e0e7", font=font(12))
    for row, key in enumerate(KEYS):
        y = header_height + row * row_height
        draw.rectangle((0, y, row_label_width - 1, y + row_height - 1), fill="#d5dce2")
        draw.text((10, y + 10), key.upper(), fill="#26313b", font=font(15))
        frames = rendered[key]["frames"]
        phases = rendered[key]["phases"]
        sample_indices = (0, 84, 144, 216)
        for column, frame_index in enumerate(sample_indices):
            x = row_label_width + column * tile_width
            draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill="#d5dce2")
            draw.text((x + 6, y + 5), f"{frame_index / FPS:0.2f}s | {phases[frame_index]}", fill="#26313b", font=font(12))
            tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            overview.paste(tile, (x, y + label_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    overview.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [overview.width, overview.height], "exists": path.is_file(), "labels_included": True}


def write_report(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Round4 Agent 04 Video Preview Report",
        "",
        "Five scene-bound prototype MP4 previews were rendered from the assigned 4x2 RGBA motion sheets.",
        "",
        "## Contract",
        "",
        f"- Videos: {len(manifest['videos'])} | resolution: 960x480 | fps: 30 | frames/video: 240 | duration: 8.00s.",
        "- Codec/pixel format: H.264/libx264, yuv420p.",
        "- Timeline: prepare -> act -> hold -> recover; contact sheets and overview contain the only labels.",
        "- Status: all assets remain `prototype`; `production_approved` is `false` for every video.",
        "",
        "## Results",
        "",
        "| Key | Video | Contact | Alpha-aware transitions | Pose cuts | Frames by phase |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in manifest["videos"]:
        transition_counts = item["transitions"]["transition_method_counts"]
        counts = item["timeline"]["frames_by_phase"]
        lines.append(
            f"| `{item['key']}` | `{Path(item['video']['path']).name}` | `{Path(item['contact_sheet']['path']).name}` | "
            f"{transition_counts.get('alpha_aware', 0)} | {item['transitions']['pose_cut_count']} | "
            f"{counts['prepare']}/{counts['act']}/{counts['hold']}/{counts['recover']} |"
        )
    lines += ["", "## Transition Methods", ""]
    for item in manifest["videos"]:
        lines.append(f"### `{item['key']}`")
        for transition in item["transitions"]["transitions"]:
            lines.append(
                f"- Cell {transition['from_cell_1_based']} -> {transition['to_cell_1_based']}: "
                f"`{transition['method']}` (alpha IoU {transition['silhouette_iou']:.4f}; {transition['reason']})."
            )
    lines += ["", "## Action-Specific Limitations", ""]
    for item in manifest["videos"]:
        lines.append(f"### `{item['key']}`")
        lines.extend(f"- {limitation}" for limitation in item["limitations"])
    lines += ["", "## Validation", "", "- All five source sheets and phase JSON files were read through the assigned group manifest."]
    lines.append("- Every MP4 was decoded and checked for resolution, fps, exact frame count, readable H.264 stream, and yuv420p when ffmpeg probing was available.")
    lines.append("- Every per-key contact sheet, group overview, and manifest path was checked for existence and consistency.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    group_manifest, sources = load_inputs(input_dir)
    background = fit_background(BACKGROUND_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: dict[str, dict[str, Any]] = {}
    video_records: list[dict[str, Any]] = []
    for key in KEYS:
        source = sources[key]
        cells = extract_cells(source["sheet_path"])
        frames, phases, timeline_report_data = render_action(key, cells, source["phase_intent"], background)
        video_path = output_dir / f"male_01_{key}_generated_round4_preview.mp4"
        contact_path = output_dir / f"male_01_{key}_generated_round4_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        contact_report = write_contact_sheet(contact_path, key, frames, phases)
        rendered[key] = {"frames": frames, "phases": phases}
        video_records.append({
            "key": key,
            "character": CHARACTER,
            "status": "prototype",
            "production_approved": False,
            "source": {
                "motion_sheet": str(source["sheet_path"]),
                "phases": str(source["phase_path"]),
                "group_manifest_key": key,
            },
            "video": video_report,
            "contact_sheet": contact_report,
            "timeline": {
                "source_phase_intent": source["phase_intent"],
                "phase_contract": list(PHASE_CONTRACT),
                **{field: timeline_report_data[field] for field in ("timeline_points", "phase_by_cell_1_based", "frames_by_phase")},
            },
            "transitions": {field: timeline_report_data[field] for field in ("transitions", "transition_method_counts", "pose_cut_count", "pose_cut_pairs_0_based", "silhouette_iou_threshold")},
            "placement": timeline_report_data["placement"],
            "limitations": LIMITATIONS[key],
        })

    overview_path = output_dir / "group_video_overview.png"
    overview_report = write_group_overview(overview_path, rendered)
    manifest = {
        "manifest_version": "generated-round4-video-1.0",
        "group": GROUP,
        "character": CHARACTER,
        "status": "prototype",
        "production_approved": False,
        "source_group_manifest": str((input_dir / "group_manifest.json").resolve()),
        "source_group_manifest_version": group_manifest.get("manifest_version"),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "format": {
            "container": "MP4",
            "codec": "H.264/libx264",
            "pixel_format": "yuv420p",
            "resolution": [WIDTH, HEIGHT],
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT,
            "timeline_contract": list(PHASE_CONTRACT),
            "camera": "fixed 960x480 camera; whole scene-bound cell placed without crop",
        },
        "videos": video_records,
        "group_overview": overview_report,
        "validation": {
            "expected_key_count": len(KEYS),
            "rendered_key_count": len(video_records),
            "all_status_prototype": all(item["status"] == "prototype" for item in video_records),
            "all_production_approved_false": all(item["production_approved"] is False for item in video_records),
            "all_contacts_exist": all(item["contact_sheet"]["exists"] for item in video_records),
            "overview_exists": overview_report["exists"],
            "manifest_consistent": [item["key"] for item in video_records] == list(KEYS),
        },
    }
    manifest_path = output_dir / "group_video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path = output_dir / "group_video_report.md"
    write_report(report_path, manifest)
    print(json.dumps({
        "videos": len(video_records),
        "contacts": sum(item["contact_sheet"]["exists"] for item in video_records),
        "overview": overview_report["exists"],
        "manifest": str(manifest_path),
        "report": str(report_path),
        "pose_cuts": {item["key"]: item["transitions"]["pose_cut_count"] for item in video_records},
    }, indent=2))


if __name__ == "__main__":
    main()
