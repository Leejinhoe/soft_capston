"""Render terrain-traversal round 4 motion sheets as review-only MP4 previews."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "assets" / "characters" / "motion_sheets" / "generated_round4" / "agent_02_terrain_traversal"
OUTPUT_DIR = ROOT / "output" / "video_previews" / "generated_round4" / "agent_02_terrain_traversal"
SOURCE_MANIFEST = INPUT_DIR / "group_manifest.json"

CHARACTER = "male_01"
ACTIONS = ("cross_bridge", "squeeze_through", "duck_under", "wade", "row")
WIDTH = 960
HEIGHT = 480
FPS = 30
FRAME_COUNT = 240
DURATION_SECONDS = 8.0
SHEET_COLUMNS = 4
SHEET_ROWS = 2
PHASE_CONTRACT = ("prepare", "act", "hold", "recover")
SILHOUETTE_IOU_THRESHOLD = 0.34

# Each action is a scene composite. The common scale is derived from all eight
# cells, while these anchors keep the terrain cue on a stable visual baseline.
SCENE_PLACEMENT = {
    "cross_bridge": {"max_height": 430, "max_width": 860, "anchor_y": 432},
    "squeeze_through": {"max_height": 430, "max_width": 860, "anchor_y": 432},
    "duck_under": {"max_height": 410, "max_width": 860, "anchor_y": 430},
    "wade": {"max_height": 430, "max_width": 860, "anchor_y": 432},
    "row": {"max_height": 365, "max_width": 860, "anchor_y": 430},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def resolve_source_path(raw_value: str, input_dir: Path) -> Path:
    raw = Path(raw_value)
    candidates = (ROOT / raw, input_dir / raw, input_dir / raw.name)
    root = input_dir.resolve()
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if root not in resolved.parents:
                raise ValueError(f"Refusing source outside assigned group: {resolved}")
            return resolved
    raise FileNotFoundError(f"Could not resolve assigned source path {raw_value!r}")


def smoothstep(value: float) -> float:
    value = min(max(float(value), 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def load_font(size: int = 16) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_background() -> Image.Image:
    """Create a quiet neutral fantasy backing for the transparent scene corners."""

    background = Image.new("RGBA", (WIDTH, HEIGHT), (20, 29, 42, 255))
    draw = ImageDraw.Draw(background, "RGBA")
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = (
            round(20 + 18 * t),
            round(29 + 28 * t),
            round(42 + 18 * t),
            255,
        )
        draw.line((0, y, WIDTH, y), fill=color)
    draw.rectangle((0, 388, WIDTH, HEIGHT), fill=(30, 52, 49, 90))
    draw.line((0, 388, WIDTH, 388), fill=(161, 177, 155, 38), width=2)
    return background


def clean_chroma_key(cell: Image.Image) -> Image.Image:
    """Remove only bright neon-green key spill left in the authored RGBA cells."""

    array = np.asarray(cell.convert("RGBA")).copy()
    red = array[..., 0].astype(np.int16)
    green = array[..., 1].astype(np.int16)
    blue = array[..., 2].astype(np.int16)
    key = (
        (array[..., 3] > 0)
        & (green > 150)
        & (green - red > 85)
        & (green - blue > 70)
        & (red < 145)
    )
    array[key, 3] = 0
    return Image.fromarray(array, "RGBA")


def extract_cells(sheet_path: Path) -> list[Image.Image]:
    with Image.open(sheet_path) as source:
        if source.mode != "RGBA":
            raise ValueError(f"Expected RGBA source sheet, got {source.mode}: {sheet_path}")
        if source.size != (1792, 1024):
            raise ValueError(f"Expected 1792x1024 source sheet, got {source.size}: {sheet_path}")
        sheet = source.copy()

    cells: list[Image.Image] = []
    for index in range(SHEET_COLUMNS * SHEET_ROWS):
        column = index % SHEET_COLUMNS
        row = index // SHEET_COLUMNS
        left = round(column * sheet.width / SHEET_COLUMNS)
        right = round((column + 1) * sheet.width / SHEET_COLUMNS)
        top = round(row * sheet.height / SHEET_ROWS)
        bottom = round((row + 1) * sheet.height / SHEET_ROWS)
        cell = clean_chroma_key(sheet.crop((left, top, right, bottom)))
        bbox = cell.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"Empty alpha cell {index + 1} in {sheet_path}")
        cells.append(cell.crop(bbox))
    return cells


def normalize_cells(action: str, cells: list[Image.Image]) -> list[Image.Image]:
    placement = SCENE_PLACEMENT[action]
    max_width = max(cell.width for cell in cells)
    max_height = max(cell.height for cell in cells)
    scale = min(
        placement["max_width"] / max(1, max_width),
        placement["max_height"] / max(1, max_height),
    )
    return [
        cell.resize(
            (max(1, round(cell.width * scale)), max(1, round(cell.height * scale))),
            Image.Resampling.LANCZOS,
        )
        for cell in cells
    ]


def aligned_canvases(first: Image.Image, second: Image.Image) -> tuple[Image.Image, Image.Image]:
    width = max(first.width, second.width)
    height = max(first.height, second.height)
    result: list[Image.Image] = []
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


def alpha_aware_interpolate(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    amount = smoothstep(amount)
    first_canvas, second_canvas = aligned_canvases(first, second)
    first_array = np.asarray(first_canvas, dtype=np.float32) / 255.0
    second_array = np.asarray(second_canvas, dtype=np.float32) / 255.0
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    alpha = first_alpha * (1.0 - amount) + second_alpha * amount
    premultiplied_rgb = first_array[..., :3] * first_alpha * (1.0 - amount)
    premultiplied_rgb += second_array[..., :3] * second_alpha * amount
    rgb = np.divide(
        premultiplied_rgb,
        np.maximum(alpha, 1e-6),
        out=np.zeros_like(premultiplied_rgb),
        where=alpha > 1e-6,
    )
    result = np.concatenate((rgb, alpha), axis=-1)
    return Image.fromarray(np.clip(result * 255.0, 0, 255).astype(np.uint8), "RGBA")


def build_transitions(cells: list[Image.Image]) -> tuple[list[dict[str, Any]], set[tuple[int, int]]]:
    transitions: list[dict[str, Any]] = []
    pose_cuts: set[tuple[int, int]] = set()
    for index, (first, second) in enumerate(zip(cells, cells[1:])):
        overlap = alpha_iou(first, second)
        method = "alpha_aware" if overlap >= SILHOUETTE_IOU_THRESHOLD else "pose_cut"
        pair = (index, index + 1)
        if method == "pose_cut":
            pose_cuts.add(pair)
        transitions.append(
            {
                "from_cell": index + 1,
                "to_cell": index + 2,
                "silhouette_iou": round(overlap, 4),
                "method": method,
            }
        )
    return transitions, pose_cuts


def build_timeline() -> list[dict[str, Any]]:
    """Return contiguous frame ranges with explicit phase durations and holds."""

    # 48 + 60 + 45 + 87 = 240 frames. Cell 5 receives a 33-frame hold and
    # the final recovery pose receives an 18-frame settle, keeping both pauses readable.
    ranges = [
        ("prepare", ((0, 18, 0, 0), (18, 48, 0, 1))),
        ("act", ((48, 60, 1, 2), (60, 96, 2, 3), (96, 108, 3, 3))),
        ("hold", ((108, 120, 3, 4), (120, 153, 4, 4))),
        ("recover", ((153, 166, 4, 5), (166, 195, 5, 6), (195, 222, 6, 7), (222, 240, 7, 7))),
    ]
    timeline: list[dict[str, Any]] = []
    for phase, entries in ranges:
        for start, end, first, second in entries:
            timeline.append(
                {
                    "start_frame": start,
                    "end_frame_exclusive": end,
                    "phase": phase,
                    "from_cell": first,
                    "to_cell": second,
                }
            )
    return timeline


def pose_at_frame(
    frame_index: int,
    cells: list[Image.Image],
    timeline: list[dict[str, Any]],
    pose_cuts: set[tuple[int, int]],
) -> tuple[Image.Image, str]:
    frame_index = min(max(frame_index, 0), FRAME_COUNT - 1)
    entry = next(item for item in timeline if item["start_frame"] <= frame_index < item["end_frame_exclusive"])
    first = int(entry["from_cell"])
    second = int(entry["to_cell"])
    if first == second:
        return cells[first], str(entry["phase"])
    denominator = max(1, int(entry["end_frame_exclusive"]) - int(entry["start_frame"]) - 1)
    amount = (frame_index - int(entry["start_frame"])) / denominator
    if (first, second) in pose_cuts:
        pose = cells[first] if amount < 0.5 else cells[second]
    else:
        pose = alpha_aware_interpolate(cells[first], cells[second], amount)
    return pose, str(entry["phase"])


def render_frames(
    action: str,
    cells: list[Image.Image],
    timeline: list[dict[str, Any]],
    pose_cuts: set[tuple[int, int]],
) -> tuple[list[Image.Image], list[str]]:
    background = make_background()
    anchor_y = int(SCENE_PLACEMENT[action]["anchor_y"])
    frames: list[Image.Image] = []
    phases: list[str] = []
    for frame_index in range(FRAME_COUNT):
        pose, phase = pose_at_frame(frame_index, cells, timeline, pose_cuts)
        frame = background.copy()
        x = round((WIDTH - pose.width) / 2)
        y = anchor_y - pose.height
        frame.alpha_composite(pose, (x, y))
        frames.append(frame.convert("RGB"))
        phases.append(phase)
    return frames, phases


def write_video(path: Path, frames: list[Image.Image]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(path),
        fps=FPS,
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
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer returned no data for {path}")


def fraction_to_float(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


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
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        probe = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=codec_name,pix_fmt,width,height,r_frame_rate,nb_read_frames,nb_frames,duration",
                "-of", "json", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        streams = json.loads(probe.stdout).get("streams") or []
        if not streams:
            raise RuntimeError(f"ffprobe found no video stream in {path}")
        stream = streams[0]
        probed_frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
        probed_fps = fraction_to_float(str(stream.get("r_frame_rate") or "0"))
        codec = str(stream.get("codec_name") or "")
        pixel_format = str(stream.get("pix_fmt") or "")
        probed_size = [int(stream.get("width", 0)), int(stream.get("height", 0))]
        duration = float(stream.get("duration") or 0.0)
        probe_source = "ffprobe"
    else:
        try:
            import imageio_ffmpeg
        except ImportError as error:
            raise RuntimeError("Neither ffprobe nor imageio_ffmpeg is available for codec validation") from error
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        probe = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"],
            check=False,
            capture_output=True,
            text=True,
        )
        probe_text = probe.stderr
        stream_match = re.search(
            r"Video:\s*([^,\s]+).*?,\s*([a-zA-Z0-9_]+)(?:\([^)]*\))?,\s*(\d+)x(\d+).*?,\s*([0-9.]+)\s*fps",
            probe_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not stream_match:
            raise RuntimeError(f"Bundled ffmpeg could not inspect video stream in {path}: {probe_text[-1000:]}")
        codec = stream_match.group(1)
        pixel_format = stream_match.group(2)
        probed_size = [int(stream_match.group(3)), int(stream_match.group(4))]
        probed_fps = float(stream_match.group(5))
        probed_frames = frame_count
        duration = frame_count / FPS
        probe_source = "bundled_ffmpeg"
    report = {
        "path": str(path.resolve()),
        "resolution": probed_size,
        "fps": round(probed_fps, 6),
        "frame_count": probed_frames,
        "duration_seconds": round(duration, 3),
        "codec": codec,
        "pixel_format": pixel_format,
        "probe_source": probe_source,
        "imageio_resolution": imageio_size,
        "imageio_fps": imageio_fps,
        "imageio_frame_count": frame_count,
        "codec_readable": first_frame is not None,
        "metadata_verified": True,
    }
    if report["resolution"] != [WIDTH, HEIGHT]:
        raise RuntimeError(f"Unexpected resolution for {path.name}: {report}")
    if abs(probed_fps - FPS) > 0.01 or abs(imageio_fps - FPS) > 0.01:
        raise RuntimeError(f"Unexpected FPS for {path.name}: {report}")
    if probed_frames != FRAME_COUNT or frame_count != FRAME_COUNT:
        raise RuntimeError(f"Unexpected frame count for {path.name}: {report}")
    if report["codec"].lower() not in {"h264", "avc1"}:
        raise RuntimeError(f"Expected H.264 codec for {path.name}: {report}")
    if report["pixel_format"] != "yuv420p":
        raise RuntimeError(f"Expected yuv420p for {path.name}: {report}")
    return report


def write_contact_sheet(
    video_path: Path,
    output_path: Path,
    action: str,
    phases: list[str],
) -> dict[str, Any]:
    reader = imageio.get_reader(str(video_path))
    try:
        count = int(reader.count_frames())
        sample_count = 12
        tile_width = 320
        tile_height = round(tile_width * HEIGHT / WIDTH)
        label_height = 30
        columns = 4
        rows = math.ceil(sample_count / columns)
        sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "#eef1f3")
        draw = ImageDraw.Draw(sheet)
        typeface = load_font(16)
        for sample in range(sample_count):
            frame_index = round(sample * max(0, count - 1) / max(1, sample_count - 1))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame = frame.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            x = (sample % columns) * tile_width
            y = (sample // columns) * (tile_height + label_height)
            sheet.paste(frame, (x, y + label_height))
            draw.rectangle((x, y, x + tile_width - 1, y + label_height - 1), fill=(227, 232, 235))
            draw.text(
                (x + 8, y + 7),
                f"{frame_index / FPS:0.2f}s  {phases[frame_index]}",
                fill=(24, 33, 39),
                font=typeface,
            )
        draw.rectangle((0, 0, sheet.width - 1, sheet.height - 1), outline=(97, 112, 120), width=2)
        draw.text((8, sheet.height - 19), f"{CHARACTER} {action} | rendered frame samples", fill=(44, 55, 61), font=load_font(13))
    finally:
        reader.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Contact sheet was not created: {output_path}")
    return {
        "path": str(output_path.resolve()),
        "sample_count": sample_count,
        "resolution": list(sheet.size),
        "labels_included": True,
        "source": "decoded rendered MP4 frames",
    }


def write_group_overview(contact_paths: list[tuple[str, Path]], output_path: Path) -> dict[str, Any]:
    tile_width, tile_height = 620, 310
    columns = 3
    rows = 2
    overview = Image.new("RGB", (columns * tile_width, rows * tile_height), "#dce2e5")
    draw = ImageDraw.Draw(overview)
    for index, (action, contact_path) in enumerate(contact_paths):
        with Image.open(contact_path) as source:
            contact = source.convert("RGB")
        scale = min((tile_width - 18) / contact.width, (tile_height - 30) / contact.height)
        resized = contact.resize((round(contact.width * scale), round(contact.height * scale)), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_width + (tile_width - resized.width) // 2
        y = (index // columns) * tile_height + (tile_height - resized.height) // 2 + 12
        overview.paste(resized, (x, y))
        draw.text(((index % columns) * tile_width + 10, (index // columns) * tile_height + 5), action, fill=(29, 40, 47), font=load_font(15))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overview.save(output_path, format="PNG", optimize=True)
    return {"path": str(output_path.resolve()), "resolution": list(overview.size), "contact_count": len(contact_paths)}


def source_risks(group_manifest: dict[str, Any], asset: dict[str, Any], phase_manifest: dict[str, Any]) -> list[str]:
    risks = [
        "Source asset remains prototype and requires animation-artist review.",
        "Scene cues are embedded in the authored composite rather than separate runtime layers.",
    ]
    if asset.get("key") == "cross_bridge":
        risks.append("Far-bank transition is more upright than a production traversal cycle.")
    elif asset.get("key") == "squeeze_through":
        risks.append("Body orientation is not perfectly continuous between all authored poses.")
    elif asset.get("key") == "duck_under":
        risks.append("Middle frames can read as a cautious crawl because of hand-to-ground support.")
    elif asset.get("key") == "wade":
        risks.append("Waterline and splash shapes vary between authored poses.")
    elif asset.get("key") == "row":
        risks.append("Two-sided stroke mechanics and boat displacement need a hand-authored pass.")
    validation = phase_manifest.get("validation")
    if isinstance(validation, dict) and validation.get("pose_readability"):
        risks.append(str(validation["pose_readability"]))
    return list(dict.fromkeys(risks))


def validate_manifest_consistency(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    assets = manifest.get("assets")
    if not isinstance(assets, list) or [item.get("key") for item in assets] != list(ACTIONS):
        raise RuntimeError("Output manifest asset order or key set is inconsistent")
    checks = []
    for asset in assets:
        video = output_dir / Path(str(asset["video"]["path"])).name
        contact = output_dir / Path(str(asset["contact_sheet"]["path"])).name
        checks.append(
            video.is_file()
            and contact.is_file()
            and asset.get("status") == "prototype"
            and asset.get("production_approved") is False
            and asset["video"]["frame_count"] == FRAME_COUNT
            and asset["video"]["resolution"] == [WIDTH, HEIGHT]
            and asset["video"]["pixel_format"] == "yuv420p"
        )
    if not all(checks):
        raise RuntimeError("Output manifest is inconsistent with generated files")
    return {"assets_checked": len(checks), "all_assets_consistent": True}


def write_report(path: Path, manifest: dict[str, Any], consistency: dict[str, Any]) -> None:
    lines = [
        "# Terrain Traversal Round 4 Video Previews",
        "",
        "Status: prototype. `production_approved` is false for all five previews.",
        "",
        "## Render Summary",
        "",
        f"- Videos: {len(manifest['assets'])} MP4 files, each 960x480 at 30 fps with 240 frames (8 seconds).",
        f"- Contact sheets: {len(manifest['assets'])}, generated from decoded rendered MP4 frames.",
        "- Group overview: one PNG composed from the five rendered contact sheets.",
        f"- Pose transitions: {manifest['transition_summary']['alpha_aware_count']} alpha-aware, {manifest['transition_summary']['pose_cut_count']} hard pose cuts.",
        f"- Manifest consistency: {consistency['all_assets_consistent']} across {consistency['assets_checked']} assets.",
        "- MP4 overlays: none. Phase and timing labels appear only in contact sheets and overview imagery.",
        "",
        "## Timeline Contract",
        "",
        "The authored phase order is preserved as prepare -> act -> hold -> recover. The rendered phase allocation is 48, 60, 45, and 87 frames respectively. The hold phase includes a 33-frame steady midpoint on cell 5; recovery ends with an 18-frame settle on cell 8.",
        "",
        "## Action Limitations",
        "",
    ]
    for asset in manifest["assets"]:
        lines.append(f"### `{asset['key']}`")
        for limitation in asset["limitations"]:
            lines.append(f"- {limitation}")
        lines.append(f"- Transition methods: {asset['transition_methods']}; pose cuts: {asset['pose_cut_count']}.")
        lines.append("")
    lines.extend(
        [
            "## Scope Policy",
            "",
            "Only the assigned `agent_02_terrain_traversal` source group and its generated output folder were read or written. Backend, Flutter, database, and other group files were not modified.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if input_dir != INPUT_DIR.resolve() or output_dir != OUTPUT_DIR.resolve():
        raise ValueError("This renderer is scoped to the assigned round4 agent_02 group and output folder")
    if not SOURCE_MANIFEST.is_file():
        raise FileNotFoundError(SOURCE_MANIFEST)

    group_manifest = read_json(SOURCE_MANIFEST)
    assets = group_manifest.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Assigned group manifest has no assets list")
    by_key = {str(item.get("key")): item for item in assets if isinstance(item, dict)}
    if set(by_key) != set(ACTIONS):
        raise ValueError(f"Expected exactly {ACTIONS}, found {sorted(by_key)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timeline = build_timeline()
    rendered_assets: list[dict[str, Any]] = []
    contact_paths: list[tuple[str, Path]] = []
    transition_counts = {"alpha_aware_count": 0, "pose_cut_count": 0}

    for action in ACTIONS:
        source_asset = by_key[action]
        sheet_path = resolve_source_path(str(source_asset["sheet_path"]), input_dir)
        phase_path = resolve_source_path(str(source_asset["phases_path"]), input_dir)
        phase_manifest = read_json(phase_path)
        phase_labels = phase_manifest.get("phase_labels")
        if phase_manifest.get("key") != action or phase_manifest.get("frame_count") != 8:
            raise ValueError(f"Phase manifest does not match {action}: {phase_path}")
        if phase_labels != ["prepare", "prepare", "act", "act", "hold", "recover", "recover", "recover"]:
            raise ValueError(f"Unexpected authored phase labels for {action}: {phase_labels}")
        cells = normalize_cells(action, extract_cells(sheet_path))
        transitions, pose_cuts = build_transitions(cells)
        transition_counts["alpha_aware_count"] += sum(item["method"] == "alpha_aware" for item in transitions)
        transition_counts["pose_cut_count"] += len(pose_cuts)
        frames, phases = render_frames(action, cells, timeline, pose_cuts)
        video_path = output_dir / f"{CHARACTER}_{action}_cycle_round4.mp4"
        contact_path = output_dir / f"{CHARACTER}_{action}_cycle_round4_contact.png"
        write_video(video_path, frames)
        video_report = validate_video(video_path)
        contact_report = write_contact_sheet(video_path, contact_path, action, phases)
        contact_paths.append((action, contact_path))
        limitations = source_risks(group_manifest, source_asset, phase_manifest)
        rendered_assets.append(
            {
                "key": action,
                "status": "prototype",
                "blocked": bool(source_asset.get("blocked", False)),
                "production_approved": False,
                "source_asset": copy.deepcopy(source_asset),
                "source_sheet": str(sheet_path),
                "source_phase_manifest": str(phase_path),
                "video": video_report,
                "contact_sheet": contact_report,
                "phase_contract": {
                    "labels_from_source": phase_labels,
                    "rendered_frame_counts": {phase: phases.count(phase) for phase in PHASE_CONTRACT},
                    "timeline": timeline,
                },
                "transition_methods": ", ".join(item["method"] for item in transitions),
                "transitions": transitions,
                "pose_cut_count": len(pose_cuts),
                "limitations": limitations,
                "quality_checks": {
                    "fixed_camera": True,
                    "scene_composite_preserved": True,
                    "per_action_scale_and_ground_anchor": SCENE_PLACEMENT[action],
                    "debug_overlay_in_mp4": False,
                    "labels_only_on_contact_sheet": True,
                    "contact_from_decoded_video": True,
                },
            }
        )

    overview_path = output_dir / "group_video_overview.png"
    overview_report = write_group_overview(contact_paths, overview_path)
    output_manifest = {
        "manifest_version": "round4-video-1.0",
        "render_status": "complete",
        "group": "terrain_traversal",
        "agent_group": "agent_02_terrain_traversal",
        "status": "prototype",
        "production_approved": False,
        "source_group_manifest": str(SOURCE_MANIFEST.resolve()),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "scope": list(ACTIONS),
        "format": {
            "resolution": [WIDTH, HEIGHT],
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "frame_count": FRAME_COUNT,
            "codec": "H.264/libx264",
            "pixel_format": "yuv420p",
            "timeline_contract": list(PHASE_CONTRACT),
            "camera": "locked centered scene-composite camera",
            "background": "neutral fantasy backing behind transparent scene corners",
        },
        "transition_policy": {
            "silhouette_iou_threshold": SILHOUETTE_IOU_THRESHOLD,
            "alpha_aware_interpolation": "premultiplied-alpha smoothstep blend on aligned bottom-centered layers",
            "pose_cut_policy": "hard cut at midpoint for adjacent cells below the overlap threshold",
        },
        "transition_summary": transition_counts,
        "assets": rendered_assets,
        "group_overview": overview_report,
        "metadata_validation": {
            "all_videos_checked": all(item["video"]["metadata_verified"] for item in rendered_assets),
            "all_codec_h264": all(item["video"]["codec"].lower() in {"h264", "avc1"} for item in rendered_assets),
            "all_yuv420p": all(item["video"]["pixel_format"] == "yuv420p" for item in rendered_assets),
            "all_resolution_960x480": all(item["video"]["resolution"] == [WIDTH, HEIGHT] for item in rendered_assets),
            "all_fps_30": all(abs(item["video"]["fps"] - FPS) <= 0.01 for item in rendered_assets),
            "all_frame_count_240": all(item["video"]["frame_count"] == FRAME_COUNT for item in rendered_assets),
            "all_contacts_exist": all(Path(item["contact_sheet"]["path"]).is_file() for item in rendered_assets),
            "asset_count": len(rendered_assets),
        },
        "output_policy": {
            "assigned_group_only": True,
            "shared_backend_modified": False,
            "flutter_modified": False,
            "database_modified": False,
            "other_asset_groups_modified": False,
            "debug_overlays_in_mp4": False,
            "labels_only_on_contact_sheets": True,
            "source_images_regenerated": False,
        },
    }
    manifest_path = output_dir / "group_video_manifest.json"
    manifest_path.write_text(json.dumps(output_manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    consistency = validate_manifest_consistency(manifest_path, output_dir)
    output_manifest["metadata_validation"]["manifest_consistency"] = consistency["all_assets_consistent"]
    manifest_path.write_text(json.dumps(output_manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    write_report(output_dir / "group_video_report.md", output_manifest, consistency)
    print(json.dumps({"render_status": "complete", "videos": len(rendered_assets), "contacts": len(contact_paths), "overview": str(overview_path.resolve()), "manifest": str(manifest_path.resolve()), "pose_cuts": transition_counts["pose_cut_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
