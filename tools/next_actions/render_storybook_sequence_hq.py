"""Render a coherent 15-second storybook sequence from the round100 assets.

This is a presentation render, separate from the per-word vocabulary previews.
It keeps the same selected character throughout and uses clean scene cuts,
independent atmospheric/prop layers, and readable action holds.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import build_round100_pack as base
import render_round100_high_quality as hq


ROOT = base.ROOT
CATALOG_PATH = ROOT / "tools" / "next_actions" / "round100_catalog.json"
OUTPUT_ROOT = ROOT / "output" / "video_final" / "storybook_hq"
VIDEO_PATH = OUTPUT_ROOT / "forest_door_adventure_15s.mp4"
CONTACT_PATH = OUTPUT_ROOT / "forest_door_adventure_contact_sheet.png"
MANIFEST_PATH = OUTPUT_ROOT / "forest_door_adventure_manifest.json"

WIDTH, HEIGHT = hq.WIDTH, hq.HEIGHT
FPS = 30
SCENE_SECONDS = 3
SCENE_FRAMES = FPS * SCENE_SECONDS
TOTAL_FRAMES = SCENE_FRAMES * 5
GROUND_Y = hq.GROUND_Y
CHARACTER_SCALE = 0.82

SCENES = (
    {"key": "journey", "group": "02_travel", "word": "여행하다"},
    {"key": "point", "group": "02_travel", "word": "가리키다"},
    {"key": "open_door", "group": "03_objects", "word": "문을 열다"},
    {"key": "open_chest", "group": "03_objects", "word": "보물상자를 열다"},
    {"key": "place_gem", "group": "03_objects", "word": "보석을 놓다"},
)


def catalog_records() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {record["key"]: record for record in data["records"]}


def lerp(first: float, second: float, amount: float) -> float:
    return first + (second - first) * min(max(amount, 0.0), 1.0)


def soft_glow(center: tuple[int, int], radius: int, color: tuple[int, int, int], opacity: int) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    x, y = center
    for size in range(radius, 2, -10):
        alpha = round(opacity * (1 - size / radius) ** 1.6)
        draw.ellipse((x - size, y - size, x + size, y + size), fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(4))


def story_scene_layer(key: str, progress: float) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    if key == "point":
        # A distant beacon gives the pointing gesture a clear target.
        layer.alpha_composite(soft_glow((805, 182), 56, (255, 215, 103), 120))
        draw.polygon([(794, 226), (816, 226), (805, 171)], fill=(255, 231, 154, 215))
        draw.ellipse((798, 163, 812, 177), fill=(255, 250, 214, 255))
    elif key == "open_door":
        layer.alpha_composite(soft_glow((650, 275), 86, (255, 221, 137), 96))
        draw.ellipse((626, 252, 674, 300), fill=(255, 244, 184, 175))
    elif key == "open_chest":
        layer.alpha_composite(soft_glow((438, 360), 78, (255, 204, 71), 110))
        for offset in (-22, 0, 22):
            draw.ellipse((438 + offset - 4, 307 - abs(offset) // 3, 438 + offset + 4, 307 - abs(offset) // 3 + 9), fill=(255, 240, 145, 220))
    elif key == "place_gem":
        pulse = 0.75 + 0.25 * math.sin(progress * math.pi * 4)
        layer.alpha_composite(soft_glow((612, 315), round(100 * pulse), (111, 210, 255), 135))
        draw.polygon([(612, 284), (631, 315), (612, 343), (593, 315)], fill=(153, 235, 255, 215), outline=(238, 255, 255, 240))
    elif key == "journey":
        # Small road highlights reinforce forward movement without adding props
        # to the character cell.
        for index in range(7):
            x = round(80 + index * 150 - progress * 110)
            draw.line((x, 425, x + 42, 425), fill=(255, 226, 156, 110), width=3)
    return layer


def atmosphere(progress: float, scene_index: int) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    # A restrained page-like atmosphere; particles are sparse and anchored to
    # the scene instead of being emitted from the character silhouette.
    for index in range(10):
        x = (index * 137 + scene_index * 47) % WIDTH
        y = 72 + ((index * 71 + scene_index * 31) % 210)
        drift = math.sin(progress * math.pi * 2 + index) * 7
        alpha = 28 + (index % 3) * 8
        draw.ellipse((x + drift - 2, y - 2, x + drift + 2, y + 2), fill=(255, 245, 192, alpha))
    return layer


def vignette() -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    for inset in range(0, 90, 10):
        alpha = round(2 + (90 - inset) * 0.12)
        draw.rectangle((inset, inset, WIDTH - inset, HEIGHT - inset), outline=(17, 22, 33, alpha), width=10)
    return layer


def transition_alpha(frame_in_scene: int) -> tuple[int, int]:
    fade = 6
    fade_in = min(frame_in_scene, fade) / fade
    fade_out = min(SCENE_FRAMES - 1 - frame_in_scene, fade) / fade
    return round(min(fade_in, fade_out) * 255), fade


def composite_scene_frame(
    *,
    scene: dict[str, Any],
    scene_index: int,
    progress: float,
    frame_in_scene: int,
    background: Image.Image,
    cells: list[Image.Image],
    vignette_layer: Image.Image,
) -> Image.Image:
    key = scene["key"]
    if key == "journey":
        background_frame = hq.background_frame(background, progress * 0.55, moving=True)
        x = round(250 + 330 * progress)
    else:
        background_frame = hq.background_frame(background, progress, moving=False)
        x = {"point": 455, "open_door": 430, "open_chest": 425, "place_gem": 425}[key]

    frame = background_frame.convert("RGBA")
    frame.alpha_composite(story_scene_layer(key, progress))
    frame.alpha_composite(atmosphere(progress, scene_index))
    pose, _, _ = hq.pose_at(cells, progress, hard_cut=True)
    pose = pose.resize((round(hq.GRID_SIZE[0] * CHARACTER_SCALE), round(hq.GRID_SIZE[1] * CHARACTER_SCALE)), Image.Resampling.LANCZOS)
    y = GROUND_Y - pose.height
    frame.alpha_composite(hq.shadow_layer(key, x, pose))
    frame.alpha_composite(pose, (x - pose.width // 2, y))
    frame.alpha_composite(vignette_layer)

    # Scene cuts are separated by a brief black page turn, avoiding a ghosted
    # full-body dissolve between unrelated poses or locations.
    visible, _ = transition_alpha(frame_in_scene)
    if visible < 255:
        veil = Image.new("RGBA", (WIDTH, HEIGHT), (8, 12, 20, 255 - visible))
        frame.alpha_composite(veil)
    return frame.convert("RGB")


def write_contact_sheet(frames: list[Image.Image]) -> None:
    tile_w, tile_h = 320, 180
    sheet = Image.new("RGB", (tile_w * 5, tile_h + 34), "#111722")
    draw = ImageDraw.Draw(sheet)
    try:
        label_font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 16)
    except OSError:
        label_font = ImageFont.load_default()
    for index, image in enumerate(frames):
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (index * tile_w + (tile_w - thumb.width) // 2, 0))
        draw.text((index * tile_w + 8, tile_h + 9), SCENES[index]["word"], fill="#f7f2df", font=label_font)
    sheet.save(CONTACT_PATH, "PNG", optimize=True)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    records = catalog_records()
    backgrounds = {
        group: hq.fit_background_source(path)
        for group, path in base.BACKGROUND_BY_GROUP.items()
        if path.is_file()
    }
    cells_by_key = {scene["key"]: hq.load_cells(Path(records[scene["key"]]["motion_sheet_path"])) for scene in SCENES}
    vignette_layer = vignette()
    contact_frames: list[Image.Image] = []

    with imageio.get_writer(
        str(VIDEO_PATH),
        fps=FPS,
        codec="libx264",
        quality=8,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    ) as writer:
        for scene_index, scene in enumerate(SCENES):
            for frame_in_scene in range(SCENE_FRAMES):
                progress = frame_in_scene / max(1, SCENE_FRAMES - 1)
                image = composite_scene_frame(
                    scene=scene,
                    scene_index=scene_index,
                    progress=progress,
                    frame_in_scene=frame_in_scene,
                    background=backgrounds[scene["group"]],
                    cells=cells_by_key[scene["key"]],
                    vignette_layer=vignette_layer,
                )
                if frame_in_scene == SCENE_FRAMES // 2:
                    contact_frames.append(image.copy())
                writer.append_data(np.asarray(image))

    write_contact_sheet(contact_frames)
    manifest = {
        "status": "rendered",
        "video": str(VIDEO_PATH),
        "contact_sheet": str(CONTACT_PATH),
        "duration_seconds": TOTAL_FRAMES / FPS,
        "format": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": TOTAL_FRAMES, "codec": "H.264/libx264"},
        "character": "male_01",
        "scenes": SCENES,
        "quality_notes": [
            "One selected character profile is used throughout.",
            "Actions are separated by readable hard scene cuts with short page-turn fades.",
            "Atmosphere, target beacon, chest glow, and gem glow are independent scene layers.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
