"""Render several coherent 15-second storybook reels from the HQ vocabulary pack."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import build_round100_pack as base
import render_round100_high_quality as hq
from render_storybook_sequence_hq import atmosphere, lerp, soft_glow, transition_alpha, vignette


ROOT = base.ROOT
CATALOG_PATH = ROOT / "tools" / "next_actions" / "round100_catalog.json"
OUTPUT_ROOT = ROOT / "output" / "video_final" / "storybook_hq" / "collection"
FPS = 30
SCENE_FRAMES = 90
TOTAL_FRAMES = SCENE_FRAMES * 5
GROUND_Y = hq.GROUND_Y
CHARACTER_SCALE = 0.82

SEQUENCES = {
    "lantern_path": {
        "title": "등불을 찾아가는 길",
        "scenes": (
            {"key": "walk", "group": "02_travel", "word": "걷다"},
            {"key": "stop", "group": "02_travel", "word": "멈추다"},
            {"key": "read_map", "group": "03_objects", "word": "지도를 읽다"},
            {"key": "open_door", "group": "03_objects", "word": "문을 열다"},
            {"key": "light_lantern", "group": "03_objects", "word": "등불을 켜다"},
        ),
    },
    "hidden_treasure": {
        "title": "숨은 보물",
        "scenes": (
            {"key": "crouch", "group": "03_objects", "word": "몸을 낮추다"},
            {"key": "uncover", "group": "03_objects", "word": "덮개를 걷다"},
            {"key": "pick_up", "group": "03_objects", "word": "주워 들다"},
            {"key": "pull_lever", "group": "03_objects", "word": "레버를 당기다"},
            {"key": "open_chest", "group": "03_objects", "word": "보물상자를 열다"},
        ),
    },
    "bridge_to_castle": {
        "title": "성으로 가는 다리",
        "scenes": (
            {"key": "journey", "group": "02_travel", "word": "여행하다"},
            {"key": "cross_bridge", "group": "02_travel", "word": "다리를 건너다"},
            {"key": "duck_under", "group": "02_travel", "word": "몸을 숙여 지나가다"},
            {"key": "point", "group": "02_travel", "word": "성 방향을 가리키다"},
            {"key": "salute", "group": "02_travel", "word": "인사하다"},
        ),
    },
}


def catalog_records() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {record["key"]: record for record in data["records"]}


def story_layer(key: str, progress: float) -> Image.Image:
    layer = Image.new("RGBA", (hq.WIDTH, hq.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    if key in {"cross_bridge", "duck_under"}:
        layer.alpha_composite(hq.scene_layer(key, progress))
    if key == "point":
        layer.alpha_composite(soft_glow((808, 182), 56, (255, 214, 105), 120))
        draw.polygon([(796, 226), (818, 226), (807, 170)], fill=(255, 231, 153, 220))
        draw.ellipse((800, 162, 814, 176), fill=(255, 250, 214, 255))
    elif key == "light_lantern":
        pulse = 0.85 + 0.15 * math.sin(progress * math.pi * 4)
        layer.alpha_composite(soft_glow((535, 310), round(95 * pulse), (255, 191, 75), 145))
        draw.ellipse((526, 298, 544, 316), fill=(255, 235, 131, 230))
    elif key == "open_chest":
        layer.alpha_composite(soft_glow((438, 360), 80, (255, 204, 71), 115))
    elif key == "pull_lever":
        layer.alpha_composite(soft_glow((620, 290), 50, (255, 220, 122), 90))
    return layer


def action_x(key: str, progress: float) -> int:
    if key in {"journey", "walk"}:
        return round(250 + 330 * progress)
    if key == "cross_bridge":
        return round(360 + 230 * progress)
    if key == "salute":
        return 455
    if key == "point":
        return 450
    if key == "duck_under":
        return 455
    return {"stop": 500, "read_map": 440, "open_door": 430, "light_lantern": 430, "crouch": 450, "uncover": 430, "pick_up": 430, "pull_lever": 430, "open_chest": 425}[key]


def background_progress(key: str, progress: float) -> tuple[bool, float]:
    if key in {"journey", "walk"}:
        return True, progress * 0.55
    return False, progress


def render_scene(
    scene: dict[str, Any],
    scene_index: int,
    progress: float,
    frame_in_scene: int,
    backgrounds: dict[str, Image.Image],
    cells: list[Image.Image],
    vignette_layer: Image.Image,
) -> Image.Image:
    key = scene["key"]
    moving, camera_progress = background_progress(key, progress)
    background = hq.background_frame(backgrounds[scene["group"]], camera_progress, moving=moving)
    frame = background.convert("RGBA")
    frame.alpha_composite(story_layer(key, progress))
    frame.alpha_composite(atmosphere(progress, scene_index + 3))
    pose, _, _ = hq.pose_at(cells, progress, hard_cut=True)
    pose = pose.resize((round(hq.GRID_SIZE[0] * CHARACTER_SCALE), round(hq.GRID_SIZE[1] * CHARACTER_SCALE)), Image.Resampling.LANCZOS)
    x = action_x(key, progress)
    y = GROUND_Y - pose.height
    frame.alpha_composite(hq.shadow_layer(key, x, pose))
    frame.alpha_composite(pose, (x - pose.width // 2, y))
    frame.alpha_composite(vignette_layer)
    visible, _ = transition_alpha(frame_in_scene)
    if visible < 255:
        frame.alpha_composite(Image.new("RGBA", (hq.WIDTH, hq.HEIGHT), (8, 12, 20, 255 - visible)))
    return frame.convert("RGB")


def write_contact_sheet(frames: list[Image.Image], scenes: tuple[dict[str, Any], ...], path: Path) -> None:
    tile_w, tile_h = 320, 180
    sheet = Image.new("RGB", (tile_w * 5, tile_h + 36), "#111722")
    draw = ImageDraw.Draw(sheet)
    try:
        label_font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 15)
    except OSError:
        label_font = ImageFont.load_default()
    for index, image in enumerate(frames):
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (index * tile_w + (tile_w - thumb.width) // 2, 0))
        draw.text((index * tile_w + 8, tile_h + 10), scenes[index]["word"], fill="#f7f2df", font=label_font)
    sheet.save(path, "PNG", optimize=True)


def render_sequence(name: str, config: dict[str, Any], record_map: dict[str, dict[str, Any]], backgrounds: dict[str, Image.Image], vignette_layer: Image.Image) -> dict[str, Any]:
    scenes = config["scenes"]
    cells_by_key = {scene["key"]: hq.load_cells(Path(record_map[scene["key"]]["motion_sheet_path"])) for scene in scenes}
    output_dir = OUTPUT_ROOT / name
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / f"{name}_15s.mp4"
    contact_path = output_dir / f"{name}_contact_sheet.png"
    contact_frames: list[Image.Image] = []
    with imageio.get_writer(str(video_path), fps=FPS, codec="libx264", quality=8, ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]) as writer:
        for scene_index, scene in enumerate(scenes):
            for frame_in_scene in range(SCENE_FRAMES):
                progress = frame_in_scene / max(1, SCENE_FRAMES - 1)
                image = render_scene(scene, scene_index, progress, frame_in_scene, backgrounds, cells_by_key[scene["key"]], vignette_layer)
                if frame_in_scene == SCENE_FRAMES // 2:
                    contact_frames.append(image.copy())
                writer.append_data(np.asarray(image))
    write_contact_sheet(contact_frames, scenes, contact_path)
    return {
        "name": name,
        "title": config["title"],
        "video": str(video_path),
        "contact_sheet": str(contact_path),
        "duration_seconds": TOTAL_FRAMES / FPS,
        "format": {"width": hq.WIDTH, "height": hq.HEIGHT, "fps": FPS, "frame_count": TOTAL_FRAMES, "codec": "H.264/libx264"},
        "character": "male_01",
        "scenes": list(scenes),
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    record_map = catalog_records()
    backgrounds = {
        group: hq.fit_background_source(path)
        for group, path in base.BACKGROUND_BY_GROUP.items()
        if path.is_file()
    }
    results = [render_sequence(name, config, record_map, backgrounds, vignette()) for name, config in SEQUENCES.items()]
    manifest = {"status": "rendered", "sequence_count": len(results), "sequences": results}
    manifest_path = OUTPUT_ROOT / "collection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
