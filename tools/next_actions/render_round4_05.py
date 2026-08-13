"""Render fantasy-device motion sheets into fixed-format prototype previews.

The renderer consumes only the assigned round4 group and writes only its
assigned preview folder. The authored scene composites stay intact as single
RGBA layers so embedded devices, terrain, and result cues remain visible.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round4" / "agent_05_fantasy_devices"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round4" / "agent_05_fantasy_devices"

CHARACTER = "male_01"
ACTIONS = ("pull_lever", "turn_dial", "place_gem", "press_seal", "light_lantern")
WIDTH = 960
HEIGHT = 480
FPS = 30
FRAME_COUNT = 240
DURATION_SECONDS = 8.0
GRID_COLUMNS = 4
GRID_ROWS = 2
PHASE_CONTRACT = ("prepare", "act", "hold", "recover")
SILHOUETTE_IOU_THRESHOLD = 0.65

# These settings keep the whole authored cell visible while giving each
# composite a readable scale and a consistent visual ground line.
PLACEMENT: dict[str, dict[str, float]] = {
    "pull_lever": {"scale": 0.88, "center_x": 480.0, "ground_y": 462.0},
    "turn_dial": {"scale": 0.88, "center_x": 474.0, "ground_y": 462.0},
    "place_gem": {"scale": 0.93, "center_x": 480.0, "ground_y": 466.0},
    "press_seal": {"scale": 0.92, "center_x": 480.0, "ground_y": 464.0},
    "light_lantern": {"scale": 0.90, "center_x": 480.0, "ground_y": 460.0},
}

# The source manifests provide the phase contract and the ordered eight-cell
# intent. These normalized positions provide readable holds between cells 5/6.
TIMELINE_PROGRESS = (0.00, 0.12, 0.25, 0.38, 0.56, 0.70, 0.86, 1.00)


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


def resolve_inside(root: Path, raw_value: str | Path) -> Path:
    raw = Path(str(raw_value))
    candidates = (raw, root / raw, root / raw.name)
    root = root.resolve()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError(f"Refusing source outside assigned folder: {resolved}")
            return resolved
    raise FileNotFoundError(f"Could not resolve source path {raw_value!r} under {root}")


def source_records(group_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = group_manifest.get("assets")
    if not isinstance(records, list):
        raise ValueError("Group manifest must contain an assets list")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not record.get("key"):
            raise ValueError("Each group asset must be an object with a key")
        result[str(record["key"])] = record
    return result


def read_action_source(
    key: str, record: dict[str, Any], input_dir: Path
) -> tuple[Path, Path, dict[str, Any]]:
    sheet_path = resolve_inside(input_dir, str(record.get("motion_sheet", "")))
    phase_path = resolve_inside(input_dir, str(record.get("phase_manifest", "")))
    phase_manifest = read_json(phase_path)
    if phase_manifest.get("word") != key:
        raise ValueError(f"Phase manifest word mismatch for {key}: {phase_path}")
    phase_intent = phase_manifest.get("phase_intent")
    if not isinstance(phase_intent, list) or len(phase_intent) != 8:
        raise ValueError(f"Expected eight phase entries for {key}")
    cells = [item.get("cell") for item in phase_intent if isinstance(item, dict)]
    phases = [str(item.get("phase")) for item in phase_intent if isinstance(item, dict)]
    if cells != list(range(1, 9)) or any(phase not in PHASE_CONTRACT for phase in phases):
        raise ValueError(f"Invalid row-major phase contract for {key}: {phase_intent}")
    if tuple(sorted(set(phases), key=PHASE_CONTRACT.index)) != PHASE_CONTRACT:
        raise ValueError(f"Missing prepare/act/hold/recover phase for {key}")
    return sheet_path, phase_path, phase_manifest


def extract_cells(sheet_path: Path) -> tuple[Image.Image, ...]:
    with Image.open(sheet_path) as source:
        sheet = source.convert("RGBA")
        if sheet.size != (1792, 1024):
            raise ValueError(f"Unexpected motion sheet size for {sheet_path}: {sheet.size}")
        cells: list[Image.Image] = []
        for index in range(8):
            left = (index % GRID_COLUMNS) * 448
            top = (index // GRID_COLUMNS) * 512
            cell = sheet.crop((left, top, left + 448, top + 512))
            if cell.getchannel("A").getbbox() is None:
                raise ValueError(f"Empty alpha cell {index + 1} in {sheet_path}")
            # Keep the fixed cell canvas. Cropping would shift embedded props.
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


def interpolate_rgba(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    amount = smoothstep(amount)
    first_array = np.asarray(first, dtype=np.float32) / 255.0
    second_array = np.asarray(second, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    rgb = first_array[..., :3] * first_alpha * (1.0 - amount)
    rgb += second_array[..., :3] * second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    return Image.fromarray(np.clip(np.concatenate((rgb, alpha), axis=-1) * 255.0, 0, 255).astype(np.uint8), "RGBA")


def make_timeline(phases: list[str]) -> tuple[tuple[float, int, str], ...]:
    return tuple((TIMELINE_PROGRESS[index], index, phases[index]) for index in range(8))


def choose_transitions(cells: tuple[Image.Image, ...]) -> tuple[list[dict[str, Any]], set[tuple[int, int]]]:
    transitions: list[dict[str, Any]] = []
    pose_cuts: set[tuple[int, int]] = set()
    for index, (first, second) in enumerate(zip(cells, cells[1:])):
        overlap = alpha_iou(first, second)
        method = "alpha_aware" if overlap >= SILHOUETTE_IOU_THRESHOLD else "pose_cut"
        pair = (index, index + 1)
        if method == "pose_cut":
            pose_cuts.add(pair)
        transitions.append({
            "from_cell_1_based": index + 1,
            "to_cell_1_based": index + 2,
            "silhouette_iou": round(overlap, 4),
            "method": method,
        })
    return transitions, pose_cuts


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
        amount = smoothstep((value - start) / max(end - start, 1e-6))
        if (first_cell, second_cell) in pose_cuts:
            pose = cells[first_cell] if amount < 0.5 else cells[second_cell]
        else:
            pose = interpolate_rgba(cells[first_cell], cells[second_cell], amount)
        return pose, first_phase if amount < 0.5 else second_phase
    return cells[-1], timeline[-1][2]


def make_background() -> Image.Image:
    # A quiet neutral slate stage keeps transparent scene corners readable.
    image = Image.new("RGBA", (WIDTH, HEIGHT), (25, 31, 42, 255))
    pixels = image.load()
    for y in range(HEIGHT):
        lift = int(10 * (1.0 - y / max(HEIGHT - 1, 1)))
        color = (25 + lift, 31 + lift, 42 + lift, 255)
        for x in range(WIDTH):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 457, WIDTH, HEIGHT), fill=(31, 37, 45, 255))
    return image


def render_frame(background: Image.Image, pose: Image.Image, placement: dict[str, float]) -> Image.Image:
    frame = background.copy()
    scale = placement["scale"]
    target_size = (round(448 * scale), round(512 * scale))
    layer = pose.resize(target_size, Image.Resampling.LANCZOS)
    center_x = placement["center_x"]
    ground_y = placement["ground_y"]
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (center_x - target_size[0] * 0.34, ground_y - 5,
         center_x + target_size[0] * 0.34, ground_y + 10),
        fill=(5, 8, 12, 80),
    )
    frame.alpha_composite(shadow)
    frame.alpha_composite(layer, (round(center_x - target_size[0] / 2), round(ground_y - target_size[1])))
    return frame.convert("RGB")


def render_action(
    key: str, cells: tuple[Image.Image, ...], phase_manifest: dict[str, Any]
) -> tuple[list[Image.Image], list[str], dict[str, Any]]:
    phase_intent = phase_manifest["phase_intent"]
    phases = [str(item["phase"]) for item in phase_intent]
    timeline = make_timeline(phases)
    transitions, pose_cuts = choose_transitions(cells)
    frames: list[Image.Image] = []
    frame_phases: list[str] = []
    background = make_background()
    placement = PLACEMENT[key]
    for frame_index in range(FRAME_COUNT):
        progress = frame_index / max(FRAME_COUNT - 1, 1)
        pose, phase = pose_at(timeline, progress, cells, pose_cuts)
        frames.append(render_frame(background, pose, placement))
        frame_phases.append(phase)
    return frames, frame_phases, {
        "timeline": [
            {"progress": progress, "cell_1_based": cell + 1, "phase": phase}
            for progress, cell, phase in timeline
        ],
        "transitions": transitions,
        "pose_cut_count": len(pose_cuts),
        "pose_cuts": [[first + 1, second + 1] for first, second in sorted(pose_cuts)],
        "silhouette_iou_threshold": SILHOUETTE_IOU_THRESHOLD,
    }


def get_font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def write_contact_sheet(path: Path, key: str, frames: list[Image.Image], phases: list[str]) -> dict[str, Any]:
    tile_width, tile_height = 240, 120
    label_height, header_height = 24, 52
    columns, rows = 4, 3
    sheet = Image.new("RGB", (columns * tile_width, header_height + rows * (tile_height + label_height)), (239, 242, 245))
    draw = ImageDraw.Draw(sheet)
    typeface = get_font()
    draw.rectangle((0, 0, sheet.width, 28), fill=(36, 47, 61))
    draw.text((8, 6), f"{CHARACTER} {key} | rendered prototype contact", fill=(255, 255, 255), font=typeface)
    draw.text((8, 32), "Samples are actual decoded MP4 frames; labels are review-only.", fill=(38, 49, 59), font=typeface)
    for sample_index in range(12):
        frame_index = min(round(sample_index * (len(frames) - 1) / 11), len(frames) - 1)
        x = (sample_index % columns) * tile_width
        y = header_height + (sample_index // columns) * (tile_height + label_height)
        tile = frames[frame_index].resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        sheet.paste(tile, (x, y + label_height))
        draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(215, 222, 228))
        draw.text((x + 7, y + 5), f"{frame_index / FPS:0.2f}s | {phases[frame_index]}", fill=(38, 49, 59), font=typeface)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [sheet.width, sheet.height], "labels_included": True, "source": "decoded_mp4_frames"}


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
        raise RuntimeError(f"Video writer returned no data: {path}")


def decode_video_frames(path: Path) -> list[Image.Image]:
    reader = imageio.get_reader(str(path))
    frames: list[Image.Image] = []
    try:
        for frame in reader:
            frames.append(Image.fromarray(frame).convert("RGB"))
    finally:
        reader.close()
    if len(frames) != FRAME_COUNT:
        raise RuntimeError(f"Decoded frame count mismatch for {path}: {len(frames)}")
    return frames


def ffmpeg_probe(path: Path) -> dict[str, Any]:
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [executable, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, check=False,
    )
    text = result.stderr
    stream_line = next((line for line in text.splitlines() if "Video:" in line), "")
    codec_match = re.search(r"Video:\s*([^,\s]+)", stream_line)
    pixel_match = re.search(r"\b(yuv\w+)", stream_line)
    size_match = re.search(r"(\d{3,4})x(\d{3,4})", stream_line)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stream_line)
    codec = codec_match.group(1) if codec_match else ""
    pixel_format = pixel_match.group(1) if pixel_match else ""
    resolution = [int(size_match.group(1)), int(size_match.group(2))] if size_match else []
    fps = float(fps_match.group(1)) if fps_match else 0.0
    return {
        "codec": codec,
        "pixel_format": pixel_format,
        "resolution": resolution,
        "fps": fps,
        "probe_stream_found": bool(stream_line),
        "probe_output": stream_line.strip(),
    }


def validate_video(path: Path) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    try:
        metadata = reader.get_meta_data()
        frame_count = int(reader.count_frames())
        first_frame = reader.get_data(0)
    finally:
        reader.close()
    imageio_fps = float(metadata.get("fps") or 0.0)
    imageio_size = list(metadata.get("size") or ())
    probe = ffmpeg_probe(path)
    codec = str(probe["codec"] or metadata.get("codec") or "")
    result = {
        "path": str(path.resolve()),
        "resolution": imageio_size,
        "fps": imageio_fps,
        "frame_count": frame_count,
        "duration_seconds": round(frame_count / imageio_fps, 3) if imageio_fps else 0.0,
        "codec": codec,
        "pixel_format": probe["pixel_format"],
        "codec_readable": first_frame is not None and probe["probe_stream_found"],
        "metadata_verified": True,
        "ffmpeg_probe": probe,
    }
    if imageio_size != [WIDTH, HEIGHT] or frame_count != FRAME_COUNT or abs(imageio_fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected MP4 metadata: {result}")
    if not any(token in codec.lower() for token in ("h264", "avc1", "264")):
        raise RuntimeError(f"Expected H.264 codec: {result}")
    if probe["pixel_format"] != "yuv420p":
        raise RuntimeError(f"Expected yuv420p pixel format: {result}")
    return result


def source_limitations(group_manifest: dict[str, Any], record: dict[str, Any], key: str) -> list[str]:
    limitations = [
        "Prototype source remains review-only; human runtime-scale review is still required.",
        "Embedded terrain/device/partner cues are preserved as one composite layer; independent parallax is unavailable.",
    ]
    report_path = INPUT_DIR / "group_report.md"
    if key == "press_seal":
        limitations.append("Medium-close source crop keeps the lower body tighter than the other device actions.")
    if key == "light_lantern":
        limitations.append("Cave vignette is embedded in the source and lighting is not a separately animated layer.")
    if key in {"pull_lever", "turn_dial", "place_gem"}:
        limitations.append("Prop and result visibility depends on the authored composite; contacts should be checked at runtime scale.")
    if report_path.is_file():
        text = report_path.read_text(encoding="utf-8")
        if "Some large composites reach a cell edge" in text:
            limitations.append("Some source composites reach a cell edge; atlas bleed and padding still need an engine check.")
    return list(dict.fromkeys(limitations))


def write_overview(path: Path, rendered: list[dict[str, Any]]) -> dict[str, Any]:
    tile_width, tile_height = 192, 108
    header_height = 44
    rows = 2
    overview = Image.new("RGB", (tile_width * len(rendered), header_height + tile_height * rows), (29, 36, 48))
    draw = ImageDraw.Draw(overview)
    typeface = get_font(15)
    for index, item in enumerate(rendered):
        x = index * tile_width
        draw.text((x + 6, 7), item["key"], fill=(255, 220, 140), font=typeface)
        draw.text((x + 6, 25), "actual MP4 frames", fill=(235, 239, 244), font=get_font(11))
        reader = imageio.get_reader(item["video"]["path"])
        try:
            first = Image.fromarray(reader.get_data(0)).convert("RGB")
            hold = Image.fromarray(reader.get_data(150)).convert("RGB")
        finally:
            reader.close()
        overview.paste(first.resize((tile_width, tile_height), Image.Resampling.LANCZOS), (x, header_height))
        overview.paste(hold.resize((tile_width, tile_height), Image.Resampling.LANCZOS), (x, header_height + tile_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    overview.save(path, format="PNG", optimize=True)
    return {"path": str(path.resolve()), "resolution": [overview.width, overview.height], "source": "decoded_mp4_frames"}


def validate_scope(input_dir: Path, output_dir: Path) -> None:
    if input_dir.resolve() != INPUT_DIR.resolve():
        raise ValueError("This renderer is scoped to the assigned fantasy_devices input folder")
    if output_dir.resolve() != OUTPUT_DIR.resolve():
        raise ValueError("This renderer is scoped to the assigned fantasy_devices output folder")


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    validate_scope(input_dir, output_dir)
    group_manifest_path = input_dir / "group_manifest.json"
    if not group_manifest_path.is_file():
        raise FileNotFoundError(group_manifest_path)
    group_manifest = read_json(group_manifest_path)
    records = source_records(group_manifest)
    missing = [key for key in ACTIONS if key not in records]
    extra = sorted(set(records) - set(ACTIONS))
    if missing or extra:
        raise ValueError(f"Assigned group manifest keys mismatch; missing={missing}, extra={extra}")
    if str(group_manifest.get("status")) != "prototype":
        raise ValueError("Source group status must remain prototype")

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, Any]] = []
    for key in ACTIONS:
        record = records[key]
        sheet_path, phase_path, phase_manifest = read_action_source(key, record, input_dir)
        cells = extract_cells(sheet_path)
        frames, phases, transition_report = render_action(key, cells, phase_manifest)
        video_path = output_dir / f"{CHARACTER}_{key}_generated_round4_preview.mp4"
        contact_path = output_dir / f"{CHARACTER}_{key}_generated_round4_preview_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        decoded_frames = decode_video_frames(video_path)
        contact_report = write_contact_sheet(contact_path, key, decoded_frames, phases)
        rendered.append({
            "key": key,
            "status": "prototype",
            "blocked": False,
            "production_approved": False,
            "review_decision": "review_only",
            "source_motion_sheet": str(sheet_path),
            "source_phase_manifest": str(phase_path),
            "source_asset": record,
            "phase_intent": phase_manifest["phase_intent"],
            "timeline": transition_report["timeline"],
            "phase_frame_counts": {phase: phases.count(phase) for phase in PHASE_CONTRACT},
            "video": video_report,
            "contact_sheet": contact_report,
            "transition_methods": transition_report,
            "limitations": source_limitations(group_manifest, record, key),
            "quality_checks": {
                "fixed_camera": True,
                "embedded_scene_preserved": True,
                "debug_overlay_in_mp4": False,
                "labels_only_on_contact_sheet_and_overview": True,
                "status_preserved": "prototype",
                "production_approved": False,
            },
        })

    overview_path = output_dir / "group_video_overview.png"
    overview_report = write_overview(overview_path, rendered)
    manifest_out = output_dir / "group_video_manifest.json"
    output_manifest = {
        "manifest_version": "round4-video-1.0",
        "render_status": "complete",
        "group": "agent_05_fantasy_devices",
        "character": CHARACTER,
        "scope": list(ACTIONS),
        "status": "prototype",
        "production_approved": False,
        "source_manifest": str(group_manifest_path),
        "source_policy": "Only the assigned agent_05_fantasy_devices round4 motion sheets and phase manifests were read.",
        "format": {
            "resolution": [WIDTH, HEIGHT],
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT,
            "codec": "H.264/libx264",
            "pixel_format": "yuv420p",
            "camera": "locked",
            "background": "neutral fantasy slate stage behind transparent composites",
            "timeline_contract": list(PHASE_CONTRACT),
        },
        "assets": rendered,
        "group_video_overview": overview_report,
        "metadata_validation": {
            "asset_count": len(rendered),
            "all_videos_checked": all(item["video"]["metadata_verified"] for item in rendered),
            "all_codec_readable": all(item["video"]["codec_readable"] for item in rendered),
            "all_h264": all(any(token in item["video"]["codec"].lower() for token in ("h264", "avc1", "264")) for item in rendered),
            "all_yuv420p": all(item["video"]["pixel_format"] == "yuv420p" for item in rendered),
            "all_resolution_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in rendered),
            "all_fps_30": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in rendered),
            "all_frame_count_240": all(item["video"]["frame_count"] == FRAME_COUNT for item in rendered),
            "all_contacts_verified": all(item["contact_sheet"]["labels_included"] for item in rendered),
            "manifest_keys_match_scope": [item["key"] for item in rendered] == list(ACTIONS),
        },
        "output_policy": {
            "only_assigned_group_written": True,
            "backend_modified": False,
            "flutter_modified": False,
            "database_modified": False,
            "other_groups_modified": False,
            "debug_overlays_in_mp4": False,
            "labels_only_on_contacts_and_overview": True,
        },
    }
    manifest_out.write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_lines = [
        "# Fantasy Devices Round 4 Video Preview Report",
        "",
        "Rendered five prototype H.264 previews from the assigned 4x2 RGBA motion sheets.",
        "",
        "## Counts",
        "",
        f"- Videos: {len(rendered)}/5",
        f"- Frames: {len(rendered) * FRAME_COUNT} total ({FRAME_COUNT} per video)",
        f"- Contacts: {len(rendered)}/5",
        "- Group overview: 1",
        "- Status: all `prototype`; `production_approved=false` for every key",
        "",
        "## Format Validation",
        "",
        "- Resolution: 960x480",
        "- Frame rate: 30 fps",
        "- Duration: 8 seconds, exactly 240 frames",
        "- Codec: H.264/libx264",
        "- Pixel format: yuv420p",
        "- Decoding: imageio and bundled ffmpeg checks passed",
        "- MP4 overlays: none; labels appear only in PNG review artifacts",
        "",
        "## Transition Methods",
        "",
    ]
    for item in rendered:
        methods = item["transition_methods"]
        counts = {method: sum(1 for transition in methods["transitions"] if transition["method"] == method) for method in ("alpha_aware", "pose_cut")}
        report_lines.append(f"- `{item['key']}`: alpha-aware {counts['alpha_aware']}, hard pose cuts {counts['pose_cut']}; cut pairs {methods['pose_cuts'] or 'none'}.")
    report_lines.extend(["", "## Action Limitations", ""])
    for item in rendered:
        report_lines.append(f"- `{item['key']}`: " + " ".join(item["limitations"]))
    report_lines.extend(["", "## Scope", "", "Only `agent_05_fantasy_devices` input/output paths and this renderer were changed."])
    (output_dir / "group_video_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"render_status": "complete", "videos": len(rendered), "contacts": len(rendered), "overview": str(overview_path.resolve()), "manifest": str(manifest_out.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
