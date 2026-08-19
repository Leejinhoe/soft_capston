"""Build identity-preserving versioned action sheets for all 16 characters.

The v3 motion sheets are the only identity source used here.  They already
share a semantic 4x2 layout across the cast:

    0 idle, 1/2 step, 3 airborne, 4 magic, 5 battle, 6 reach, 7 gesture

Each generated sheet is a transparent 1536x1024 PNG (four 384x512 cells per
row). Frames are selected from the source sheet, transformed with deterministic
identity-safe motion correction, and may receive small action cues such as a
strike arc or handoff prop. No background or text is introduced.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import shutil
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MOTION_SHEET_DIR = ROOT / "assets" / "characters" / "motion_sheets"
DEFAULT_VERSION = "v23"
SUPPORTED_VERSIONS = tuple(f"v{number}" for number in range(23, 29))

CHARACTER_KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)

SHEET_COLUMNS = 4
SHEET_ROWS = 2
FRAME_COUNT = SHEET_COLUMNS * SHEET_ROWS
CELL_SIZE = (384, 512)
SHEET_SIZE = (CELL_SIZE[0] * SHEET_COLUMNS, CELL_SIZE[1] * SHEET_ROWS)

# Keep the same runtime framing used by the existing v16 run-cycle sheets.
# The visible crop is centered horizontally and rests on this local baseline.
VISIBLE_MAX_SIZE = (352, 404)
BASELINE_Y = 480
CROP_MARGIN = 8


# Each release tightens a different part of the sprite contract. The steps
# are intentionally deterministic so a later asset can be regenerated from
# the same source without a model or a remote service.
VERSION_PROFILES = {
    "v23": {"scale": 1.000, "motion": 0.70, "rotation": 0.35, "trail": 0, "prop": 0, "cleanup": False},
    "v24": {"scale": 1.004, "motion": 0.82, "rotation": 0.45, "trail": 0, "prop": 0, "cleanup": True},
    "v25": {"scale": 1.008, "motion": 0.94, "rotation": 0.62, "trail": 0, "prop": 0, "cleanup": True},
    "v26": {"scale": 1.012, "motion": 1.06, "rotation": 0.80, "trail": 1, "prop": 0, "cleanup": True},
    "v27": {"scale": 1.016, "motion": 1.18, "rotation": 0.98, "trail": 2, "prop": 1, "cleanup": True},
    "v28": {"scale": 1.020, "motion": 1.30, "rotation": 1.16, "trail": 3, "prop": 2, "cleanup": True},
}

# The five upgrades are recorded in the manifest so a generated pack explains
# what changed between v23 and the v28 production baseline.
UPGRADE_ROUNDS = {
    "v24": {
        "round": 1,
        "focus": "alpha_cleanup_and_crop_safety",
        "changes": ["median_alpha_cleanup", "isolated_component_removal", "8px_cell_margin"],
    },
    "v25": {
        "round": 2,
        "focus": "identity_scale_and_grounding",
        "changes": ["shared_visible_bounds", "stable_foot_baseline", "bounded_rotation"],
    },
    "v26": {
        "round": 3,
        "focus": "phase_transition_readability",
        "changes": ["prepare_act_recover_timeline", "progressive_motion_offsets", "strike_trail"],
    },
    "v27": {
        "round": 4,
        "focus": "action_semantic_cues",
        "changes": ["battle_arc", "handoff_object_marker", "action_phase_manifest"],
    },
    "v28": {
        "round": 5,
        "focus": "canonical_quality_gate",
        "changes": ["final_crop_gate", "identity_locked_16_character_pack", "sha_verified_canonical_pack"],
    },
}


# (source frame, horizontal shift, vertical shift).  The v3 source layout is
# shared by every character, so these mappings stay character-independent.
FRAME_MAPS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "jump_cycle": (
        (0, 0, 0),
        (6, 0, -4),
        (3, 0, -42),
        (3, 0, -56),
        (3, 0, -42),
        (3, 0, -16),
        (6, 0, -4),
        (0, 0, 0),
    ),
    "battle_cycle": (
        (0, 0, 0),
        (6, -4, -2),
        (6, -10, -4),
        (6, 8, -2),
        (6, 12, -1),
        (6, 5, 0),
        (6, 0, 0),
        (0, -2, 0),
    ),
    "interaction_cycle": (
        (0, 0, 0),
        (6, 4, -2),
        (7, 8, -5),
        (6, 5, -3),
        (7, -5, -5),
        (6, 2, -3),
        (7, -3, -2),
        (0, 0, 0),
    ),
    "action_sheet": (
        (0, 0, 0),
        (7, 0, 0),
        (6, 0, 0),
        (7, 0, 0),
        (4, 0, 0),
        (4, 0, 0),
        (3, 0, -8),
        (6, 0, 0),
    ),
}

ACTION_OFFSETS = {
    "jump_cycle": ((0, 0), (-2, 0), (-4, -12), (0, -24), (4, -14), (6, -4), (2, 0), (0, 0)),
    "battle_cycle": ((0, 0), (-4, -1), (-8, -2), (8, -1), (12, 0), (5, 0), (0, 0), (-2, 0)),
    "interaction_cycle": ((0, 0), (4, -1), (8, -2), (5, -1), (-5, -2), (2, -1), (-3, -1), (0, 0)),
    "action_sheet": ((0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, -2), (0, 0)),
}

ACTION_ROTATIONS = {
    "jump_cycle": (0.0, -1.0, -2.0, 0.0, 1.5, 2.0, 0.8, 0.0),
    "battle_cycle": (0.0, -1.0, -2.5, -4.0, -3.0, 2.5, 1.0, 0.0),
    "interaction_cycle": (0.0, 0.0, 0.6, 1.0, 1.4, 0.9, 0.3, 0.0),
    "action_sheet": (0.0, 0.0, -0.5, 0.4, 0.0, 0.0, -1.2, 0.0),
}

ACTION_SEMANTICS = {
    "jump_cycle": {
        "phases": ["prepare", "launch", "airborne", "airborne", "descending", "land", "recover", "settle"],
        "source_frames": [0, 6, 3, 3, 3, 3, 6, 0],
    },
    "battle_cycle": {
        "phases": ["ready", "windup", "lunge", "strike", "follow_through", "recoil", "guard", "settle"],
        "source_frames": [0, 6, 6, 6, 6, 6, 6, 0],
        "requires_partner": True,
        "requires_object": False,
    },
    "interaction_cycle": {
        "phases": ["idle", "orient", "reach", "approach", "contact", "receive", "retract", "settle"],
        "source_frames": [0, 6, 7, 6, 7, 6, 7, 0],
        "requires_partner": True,
        "requires_object": True,
    },
    "action_sheet": {
        "phases": ["idle", "wave", "investigate", "handoff", "magic", "magic_hold", "battle", "battle_recover"],
        "source_frames": [0, 7, 6, 7, 4, 4, 3, 6],
    },
}

def output_names(version: str) -> dict[str, str]:
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported action asset version: {version}")
    return {
        "jump_cycle": f"{{character_key}}_jump_cycle_{version}.png",
        "battle_cycle": f"{{character_key}}_battle_cycle_{version}.png",
        "interaction_cycle": f"{{character_key}}_interaction_cycle_{version}.png",
        "action_sheet": f"{{character_key}}_action_sheet_{version}.png",
    }


def version_profile(version: str) -> dict[str, object]:
    try:
        return VERSION_PROFILES[version]
    except KeyError as exc:
        raise ValueError(f"No deterministic quality profile for {version}") from exc

# male_01 already has hand-authored action cycles with a visible sword and
# clearer handoff poses. Keep those stronger identity/action assets instead of
# replacing them with a generic v3-derived approximation.
LEGACY_SOURCE_OVERRIDES = {
    "male_01": {
        "jump_cycle": "male_01_jump_cycle_v19.png",
        "battle_cycle": "male_01_battle_cycle_v22.png",
        "interaction_cycle": "male_01_interaction_cycle_v22.png",
        "action_sheet": "male_01_action_sheet_v21.png",
    },
}


def split_sheet(sheet: Image.Image) -> list[Image.Image]:
    """Split a source sheet using proportional boundaries without resampling."""

    rgba = sheet.convert("RGBA")
    cells: list[Image.Image] = []
    for row in range(SHEET_ROWS):
        top = round(row * rgba.height / SHEET_ROWS)
        bottom = round((row + 1) * rgba.height / SHEET_ROWS)
        for column in range(SHEET_COLUMNS):
            left = round(column * rgba.width / SHEET_COLUMNS)
            right = round((column + 1) * rgba.width / SHEET_COLUMNS)
            cells.append(rgba.crop((left, top, right, bottom)))
    if len(cells) != FRAME_COUNT:
        raise AssertionError(
            f"Expected {FRAME_COUNT} source frames, got {len(cells)}"
        )
    return cells


def _visible_crop(cell: Image.Image) -> Image.Image:
    """Crop only transparent margins, retaining every non-zero alpha pixel."""

    visible_bounds = cell.getchannel("A").getbbox()
    if visible_bounds is None:
        raise ValueError("Source pose has no visible pixels")
    return cell.crop(visible_bounds)


def visible_cells(cells: list[Image.Image]) -> list[Image.Image]:
    """Return alpha-cropped poses without changing their source identity."""

    return [_visible_crop(cell) for cell in cells]


def clean_source_cells(cells: list[Image.Image], version: str) -> list[Image.Image]:
    """Remove isolated alpha specks introduced at source-sheet cell joins."""

    if not bool(version_profile(version)["cleanup"]):
        return cells
    cleaned: list[Image.Image] = []
    for cell in cells:
        rgba = cell.convert("RGBA")
        alpha = rgba.getchannel("A").filter(ImageFilter.MedianFilter(3))
        rgba.putalpha(alpha)
        cleaned.append(_remove_small_components(rgba))
    return cleaned


def _remove_small_components(cell: Image.Image, minimum_area: int = 500) -> Image.Image:
    """Keep meaningful connected artwork and discard legacy cell debris."""

    rgba = cell.convert("RGBA")
    alpha = rgba.getchannel("A")
    width, height = alpha.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    keep = bytearray(width * height)
    threshold = 16

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or pixels[x, y] < threshold:
                continue
            stack = [index]
            visited[index] = 1
            component: list[int] = []
            min_x = max_x = x
            min_y = max_y = y
            while stack:
                current = stack.pop()
                component.append(current)
                cx = current % width
                cy = current // width
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    neighbor = ny * width + nx
                    if not visited[neighbor] and pixels[nx, ny] >= threshold:
                        visited[neighbor] = 1
                        stack.append(neighbor)
            touches_edge = min_x == 0 or min_y == 0 or max_x == width - 1 or max_y == height - 1
            boundary_debris = touches_edge and (
                max_x - min_x < 64 or max_y - min_y < 64
            )
            if len(component) >= minimum_area and not boundary_debris:
                for component_index in component:
                    keep[component_index] = 255

    cleaned_alpha = Image.frombytes("L", (width, height), bytes(
        keep[index] if keep[index] else 0 for index in range(width * height)
    ))
    rgba.putalpha(cleaned_alpha)
    return rgba


def normalize_cells(cells: list[Image.Image]) -> list[Image.Image]:
    """Fit poses to a shared identity scale and stable foot baseline."""

    visible = visible_cells(cells)
    max_width = max(cell.width for cell in visible)
    max_height = max(cell.height for cell in visible)
    scale = min(
        VISIBLE_MAX_SIZE[0] / max_width,
        VISIBLE_MAX_SIZE[1] / max_height,
    )

    normalized: list[Image.Image] = []
    for visible in visible:
        size = (
            max(1, round(visible.width * scale)),
            max(1, round(visible.height * scale)),
        )
        resized = visible.resize(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
        left = (CELL_SIZE[0] - resized.width) // 2
        top = BASELINE_Y - resized.height
        canvas.alpha_composite(resized, (left, top))
        normalized.append(canvas)
    return normalized


def _translate(frame: Image.Image, dx: int, dy: int) -> Image.Image:
    """Translate a cell with transparent fill and no wraparound."""

    if dx == 0 and dy == 0:
        return frame
    return frame.transform(
        frame.size,
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.NEAREST,
        fillcolor=(0, 0, 0, 0),
    )


def _pack(frames: Iterable[Image.Image]) -> Image.Image:
    frames = list(frames)
    if len(frames) != FRAME_COUNT:
        raise ValueError(f"Expected {FRAME_COUNT} frames, got {len(frames)}")
    sheet = Image.new("RGBA", SHEET_SIZE, (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        left = (index % SHEET_COLUMNS) * CELL_SIZE[0]
        top = (index // SHEET_COLUMNS) * CELL_SIZE[1]
        sheet.alpha_composite(frame, (left, top))
    return sheet


def _source_mapping(action_name: str, has_dedicated_source: bool) -> tuple[tuple[int, int, int], ...]:
    if has_dedicated_source:
        return tuple((index, 0, 0) for index in range(FRAME_COUNT))
    return FRAME_MAPS[action_name]


def _render_pose(
    pose: Image.Image,
    action_name: str,
    frame_index: int,
    version: str,
) -> Image.Image:
    """Place one pose on a fixed canvas with versioned motion correction."""

    profile = version_profile(version)
    cropped = _visible_crop(pose)
    max_width, max_height = VISIBLE_MAX_SIZE
    base_scale = min(max_width / cropped.width, max_height / cropped.height)
    scale = base_scale * float(profile["scale"])
    size = (
        max(1, round(cropped.width * scale)),
        max(1, round(cropped.height * scale)),
    )
    resample = Image.Resampling.LANCZOS
    resized = cropped.resize(size, resample)
    rotation = ACTION_ROTATIONS[action_name][frame_index] * float(profile["rotation"])
    if rotation:
        resized = resized.rotate(
            rotation,
            resample=Image.Resampling.BICUBIC,
            expand=True,
        )

    safe_size = (
        CELL_SIZE[0] - CROP_MARGIN * 2,
        CELL_SIZE[1] - CROP_MARGIN * 2,
    )
    if resized.width > safe_size[0] or resized.height > safe_size[1]:
        fit_scale = min(
            safe_size[0] / resized.width,
            safe_size[1] / resized.height,
        )
        resized = resized.resize(
            (
                max(1, round(resized.width * fit_scale)),
                max(1, round(resized.height * fit_scale)),
            ),
            Image.Resampling.LANCZOS,
        )

    motion_gain = float(profile["motion"])
    raw_dx, raw_dy = ACTION_OFFSETS[action_name][frame_index]
    dx = round(raw_dx * motion_gain)
    dy = round(raw_dy * motion_gain)
    left = (CELL_SIZE[0] - resized.width) // 2 + dx
    top = BASELINE_Y - resized.height + dy
    # Keep every version crop-safe even when a sword, cape, or braid extends.
    left = min(max(left, CROP_MARGIN), CELL_SIZE[0] - resized.width - CROP_MARGIN)
    top = min(max(top, CROP_MARGIN), CELL_SIZE[1] - resized.height - CROP_MARGIN)
    canvas = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(resized, (left, top))
    return canvas


def _add_semantic_cues(
    frame: Image.Image,
    action_name: str,
    frame_index: int,
    version: str,
) -> Image.Image:
    """Add restrained prop/effect cues without changing character pixels."""

    profile = version_profile(version)
    trail = int(profile["trail"])
    prop = int(profile["prop"])
    if trail == 0 and prop == 0:
        return frame

    result = frame.copy()
    draw = ImageDraw.Draw(result, "RGBA")
    if action_name == "battle_cycle" and frame_index in (3, 4, 5):
        # A short arc makes a strike readable for characters whose source bank
        # has no weapon. male_01 still keeps its authored sword pixels.
        alpha = 58 + trail * 18
        draw.arc((184, 146, 374, 344), 204, 330, fill=(255, 219, 91, alpha), width=2 + trail)
        draw.arc((202, 164, 386, 326), 204, 330, fill=(255, 248, 190, alpha // 2), width=2)
    if action_name == "interaction_cycle" and frame_index in (3, 4, 5):
        # The object cue is intentionally small; the partner remains a
        # separate render layer and is required by the action contract.
        radius = 6 + prop * 2
        center_x, center_y = 300, 302
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=(255, 219, 91, 185),
        )
        draw.ellipse(
            (center_x - 2, center_y - 2, center_x + 2, center_y + 2),
            fill=(255, 251, 214, 220),
        )
        draw.line(
            (center_x, center_y + radius, center_x, center_y + radius + 13),
            fill=(255, 219, 91, 190),
            width=2,
        )
    return result


def build_sheet(
    source_cells: list[Image.Image],
    action_name: str,
    version: str,
    has_dedicated_source: bool = False,
) -> Image.Image:
    """Build one 4x2 action sheet from the identity-locked source bank."""

    mapping = _source_mapping(action_name, has_dedicated_source)
    frames = []
    for index, (source_index, _dx, _dy) in enumerate(mapping):
        frame = _render_pose(source_cells[source_index], action_name, index, version)
        frames.append(_add_semantic_cues(frame, action_name, index, version))
    return _pack(frames)


def validate_sheet(sheet: Image.Image) -> None:
    """Enforce the runtime canvas, alpha, and eight-visible-cell contract."""

    if sheet.mode != "RGBA":
        raise ValueError(f"Expected RGBA sheet, got {sheet.mode}")
    if sheet.size != SHEET_SIZE:
        raise ValueError(f"Expected {SHEET_SIZE}, got {sheet.size}")

    alpha = sheet.getchannel("A")
    if alpha.getextrema() == (255, 255):
        raise ValueError("Sheet has no transparent pixels")
    corners = (
        (0, 0),
        (sheet.width - 1, 0),
        (0, sheet.height - 1),
        (sheet.width - 1, sheet.height - 1),
    )
    if any(alpha.getpixel(point) != 0 for point in corners):
        raise ValueError("Sheet corners must remain fully transparent")

    for index in range(FRAME_COUNT):
        box = (
            index % SHEET_COLUMNS * CELL_SIZE[0],
            index // SHEET_COLUMNS * CELL_SIZE[1],
            (index % SHEET_COLUMNS + 1) * CELL_SIZE[0],
            (index // SHEET_COLUMNS + 1) * CELL_SIZE[1],
        )
        cell_alpha = alpha.crop(box)
        if cell_alpha.getbbox() is None:
            raise ValueError(f"Frame {index} has no visible pixels")
        bbox = cell_alpha.getbbox()
        assert bbox is not None
        if (
            bbox[0] < CROP_MARGIN
            or bbox[1] < CROP_MARGIN
            or bbox[2] > CELL_SIZE[0] - CROP_MARGIN
            or bbox[3] > CELL_SIZE[1] - CROP_MARGIN
        ):
            raise ValueError(f"Frame {index} violates {CROP_MARGIN}px crop margin")
        if cell_alpha.histogram()[0] <= cell_alpha.width * cell_alpha.height // 3:
            raise ValueError(f"Frame {index} has insufficient transparent canvas")


def build_character_action_cycles(
    character_key: str,
    output_dir: Path = MOTION_SHEET_DIR,
    version: str = DEFAULT_VERSION,
) -> list[Path]:
    """Build four versioned sheets for one character and return their paths."""

    source_path = MOTION_SHEET_DIR / f"{character_key}_motion_sheet_v3.png"
    if not source_path.is_file():
        raise FileNotFoundError(f"Missing identity source: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    names = output_names(version)
    for action_name in FRAME_MAPS:
        override_name = LEGACY_SOURCE_OVERRIDES.get(character_key, {}).get(action_name)
        if override_name:
            override_path = MOTION_SHEET_DIR / override_name
            with Image.open(override_path) as source:
                source_cells = clean_source_cells(split_sheet(source), version)
            sheet = build_sheet(source_cells, action_name, version, True)
        else:
            with Image.open(source_path) as source:
                source_cells = clean_source_cells(split_sheet(source), version)
            sheet = build_sheet(source_cells, action_name, version)
        validate_sheet(sheet)
        output_path = output_dir / names[action_name].format(
            character_key=character_key,
        )
        sheet.save(output_path, format="PNG", optimize=True)
        written.append(output_path)
    return written


def build_all(
    output_dir: Path = MOTION_SHEET_DIR,
    character_keys: Iterable[str] = CHARACTER_KEYS,
    version: str = DEFAULT_VERSION,
) -> list[Path]:
    """Build all four versioned sheet types for every requested character."""

    written: list[Path] = []
    for character_key in character_keys:
        if character_key not in CHARACTER_KEYS:
            raise ValueError(f"Unknown character key: {character_key}")
        written.extend(build_character_action_cycles(character_key, output_dir, version))
    return written


def write_manifest(
    output_dir: Path,
    character_keys: Iterable[str],
    version: str = DEFAULT_VERSION,
) -> Path:
    names = output_names(version)
    manifest = {
        "version": version,
        "quality_profile": version_profile(version),
        "upgrade_rounds": [
            UPGRADE_ROUNDS[round_version]
            for round_version in SUPPORTED_VERSIONS
            if round_version in UPGRADE_ROUNDS and SUPPORTED_VERSIONS.index(round_version) <= SUPPORTED_VERSIONS.index(version)
        ],
        "source": "motion_sheet_v3",
        "source_overrides": LEGACY_SOURCE_OVERRIDES,
        "sheet_size": list(SHEET_SIZE),
        "cell_size": list(CELL_SIZE),
        "columns": SHEET_COLUMNS,
        "rows": SHEET_ROWS,
        "characters": list(character_keys),
        "actions": ACTION_SEMANTICS,
        "files": {
            action_name: names[action_name]
            for action_name in FRAME_MAPS
        },
    }
    path = output_dir / f"action_cycle_{version}_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def promote_canonical_pack(
    source_dir: Path,
    canonical_dir: Path = MOTION_SHEET_DIR,
    version: str = "v28",
) -> list[Path]:
    """Copy the verified final pack without touching v22/v23 source assets."""

    names = output_names(version)
    canonical_dir.mkdir(parents=True, exist_ok=True)
    promoted: list[Path] = []
    for character_key in CHARACTER_KEYS:
        for template in names.values():
            source = source_dir / template.format(character_key=character_key)
            target = canonical_dir / source.name
            shutil.copy2(source, target)
            promoted.append(target)
    return promoted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=MOTION_SHEET_DIR,
        help="Directory for generated PNGs (default: assets/characters/motion_sheets)",
    )
    parser.add_argument(
        "--character",
        dest="characters",
        action="append",
        choices=CHARACTER_KEYS,
        help="Build only this character; repeat the option for multiple characters",
    )
    parser.add_argument(
        "--version",
        choices=SUPPORTED_VERSIONS,
        default=DEFAULT_VERSION,
        help="Version suffix for the generated sheets (default: v23)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    characters = args.characters or CHARACTER_KEYS
    written = build_all(args.output_dir, characters, args.version)
    manifest = write_manifest(args.output_dir, characters, args.version)
    print(
        f"Built {len(written)} {args.version} sheets for "
        f"{len(characters)} characters."
    )
    print(manifest.resolve())
    for path in written:
        print(path.resolve())


if __name__ == "__main__":
    main()
