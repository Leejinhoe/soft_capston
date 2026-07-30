import math
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple


STAGE_ID = "enchanted-root-seal"
OBSTACLE_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "props"
    / "enchanted_root_obstacle_v1.png"
)


def _smoothstep(value: float) -> float:
    normalized = min(1.0, max(0.0, value))
    return normalized * normalized * (3.0 - 2.0 * normalized)


def supports_story_stage(
    action_names: Sequence[str],
    story_text: Optional[str] = None,
) -> bool:
    normalized = tuple(str(name).strip().lower() for name in action_names)
    has_approach = any(name in {"walk", "run"} for name in normalized)
    has_actions = has_approach and "jump" in normalized and "magic" in normalized
    if not has_actions or story_text is None:
        return has_actions
    normalized_story = " ".join(story_text.lower().split())
    obstacle_keywords = (
        "root",
        "bramble",
        "thorn",
        "vine",
        "fallen tree",
        "log",
        "obstacle",
        "barrier",
        "blocked",
        "seal",
        "\ubfcc\ub9ac",
        "\uac00\uc2dc",
        "\ub369\uad74",
        "\ud1b5\ub098\ubb34",
        "\uc7a5\uc560\ubb3c",
        "\ubd09\uc778",
        "\uae38\uc744 \ub9c9",
    )
    return any(keyword in normalized_story for keyword in obstacle_keywords)


def prepare_story_stage(
    action_names: Sequence[str],
    Image,
    *,
    width: int,
    height: int,
    story_text: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if (
        not supports_story_stage(action_names, story_text)
        or not OBSTACLE_PATH.exists()
    ):
        return None

    with Image.open(OBSTACLE_PATH) as source:
        prop = source.convert("RGBA")
    target_width = max(1, round(width * 0.34))
    scale = target_width / prop.width
    prop = prop.resize(
        (target_width, max(1, round(prop.height * scale))),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    position = (
        round(width * 0.43),
        round(height * 0.87) - prop.height,
    )
    target = (
        position[0] + round(prop.width * 0.5),
        position[1] - round(prop.height * 0.08),
    )
    return {
        "id": STAGE_ID,
        "prop": prop,
        "position": position,
        "target": target,
        "action_names": list(action_names),
    }


def story_stage_state(
    action_name: Optional[str],
    action_progress: float,
) -> Dict[str, float]:
    progress = min(1.0, max(0.0, action_progress))
    idle_pulse = 0.16 + 0.06 * math.sin(math.tau * progress * 2.0)
    if action_name != "magic":
        awareness = (
            _smoothstep((progress - 0.76) / 0.18)
            if action_name in {"walk", "run"}
            else 0.0
        )
        return {
            "prop_opacity": 1.0,
            "seal_glow": min(1.0, idle_pulse + awareness * 0.55),
            "beam_strength": 0.0,
            "impact_strength": 0.0,
            "success_strength": 0.0,
            "landing_strength": (
                math.sin(math.pi * (progress - 0.76) / 0.2)
                if action_name == "jump" and 0.76 <= progress <= 0.96
                else 0.0
            ),
        }

    charge = _smoothstep((progress - 0.24) / 0.22)
    release = 1.0 - _smoothstep((progress - 0.7) / 0.12)
    beam_strength = charge * release
    impact_strength = math.exp(-((progress - 0.62) / 0.1) ** 2)
    success_strength = _smoothstep((progress - 0.6) / 0.18)
    return {
        "prop_opacity": max(0.0, 1.0 - success_strength),
        "seal_glow": min(
            1.0,
            idle_pulse + charge * 0.55 + impact_strength * 0.55,
        ),
        "beam_strength": beam_strength,
        "impact_strength": impact_strength,
        "success_strength": success_strength,
        "landing_strength": 0.0,
    }


def _glow_sprite(Image, ImageDraw, ImageFilter, radius: int, strength: float):
    radius = max(4, int(radius))
    size = radius * 2
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    alpha = round(210 * min(1.0, max(0.0, strength)))
    draw.ellipse(
        (radius * 0.3, radius * 0.3, radius * 1.7, radius * 1.7),
        fill=(80, 210, 255, alpha),
    )
    return glow.filter(ImageFilter.GaussianBlur(max(2, radius * 0.28)))


def compose_story_stage_background(
    background,
    stage: Optional[Dict[str, Any]],
    *,
    action_name: Optional[str],
    action_progress: float,
    Image,
    ImageDraw,
    ImageFilter,
):
    if stage is None:
        return background

    state = story_stage_state(action_name, action_progress)
    composed = background.copy().convert("RGBA")
    target_x, target_y = stage["target"]
    success_strength = state["success_strength"]
    if success_strength > 0.0:
        opened_path = Image.new("RGBA", composed.size, (0, 0, 0, 0))
        path_draw = ImageDraw.Draw(opened_path)
        castle_point = (
            round(composed.width * 0.67),
            round(composed.height * 0.2),
        )
        path_start = (
            target_x,
            round(composed.height * 0.84),
        )
        trail_points = (
            path_start,
            (round(composed.width * 0.56), round(composed.height * 0.68)),
            (round(composed.width * 0.63), round(composed.height * 0.57)),
            (round(composed.width * 0.60), round(composed.height * 0.47)),
            (round(composed.width * 0.68), round(composed.height * 0.38)),
            castle_point,
        )
        path_width = max(7, round(composed.width * 0.026))
        path_draw.line(
            trail_points,
            fill=(255, 219, 105, round(86 * success_strength)),
            width=path_width,
            joint="curve",
        )
        for index, point in enumerate(trail_points[:-1]):
            radius = max(3, round(path_width * (0.5 - index * 0.045)))
            path_draw.ellipse(
                (
                    point[0] - radius,
                    point[1] - radius,
                    point[0] + radius,
                    point[1] + radius,
                ),
                fill=(255, 239, 168, round(145 * success_strength)),
            )
        opened_path = opened_path.filter(
            ImageFilter.GaussianBlur(max(4, round(path_width * 0.7)))
        )
        composed.alpha_composite(opened_path)
        path_core = Image.new("RGBA", composed.size, (0, 0, 0, 0))
        core_draw = ImageDraw.Draw(path_core)
        core_draw.line(
            trail_points,
            fill=(255, 245, 190, round(72 * success_strength)),
            width=max(2, round(path_width * 0.28)),
            joint="curve",
        )
        composed.alpha_composite(path_core)

    glow_radius = max(12, round(composed.width * 0.045))
    glow = _glow_sprite(
        Image,
        ImageDraw,
        ImageFilter,
        glow_radius,
        state["seal_glow"],
    )
    composed.alpha_composite(
        glow,
        (target_x - glow.width // 2, target_y - glow.height // 2),
    )

    prop = stage["prop"]
    opacity = state["prop_opacity"]
    if opacity < 0.999:
        prop = prop.copy()
        prop.putalpha(
            prop.getchannel("A").point(
                lambda value: round(value * opacity)
            )
        )
    composed.alpha_composite(prop, stage["position"])

    seal_visibility = max(0.0, 1.0 - success_strength)
    if seal_visibility > 0.01:
        seal_radius = max(16, round(composed.width * 0.06))
        seal = Image.new(
            "RGBA",
            (seal_radius * 2 + 8, seal_radius * 2 + 8),
            (0, 0, 0, 0),
        )
        seal_draw = ImageDraw.Draw(seal)
        center = seal.width // 2
        alpha = round(238 * seal_visibility)
        for radius_scale, width_scale in ((1.0, 0.09), (0.68, 0.07)):
            radius = round(seal_radius * radius_scale)
            seal_draw.ellipse(
                (
                    center - radius,
                    center - radius,
                    center + radius,
                    center + radius,
                ),
                outline=(95, 220, 255, alpha),
                width=max(2, round(seal_radius * width_scale)),
            )
        for index in range(8):
            angle = math.tau * index / 8.0
            inner = seal_radius * 0.72
            outer = seal_radius * 0.95
            seal_draw.line(
                (
                    center + math.cos(angle) * inner,
                    center + math.sin(angle) * inner,
                    center + math.cos(angle) * outer,
                    center + math.sin(angle) * outer,
                ),
                fill=(255, 225, 100, alpha),
                width=max(2, round(seal_radius * 0.06)),
            )
        diamond_radius = seal_radius * 0.35
        seal_draw.polygon(
            (
                (center, center - diamond_radius),
                (center + diamond_radius, center),
                (center, center + diamond_radius),
                (center - diamond_radius, center),
            ),
            outline=(255, 239, 155, alpha),
            width=max(2, round(seal_radius * 0.055)),
        )
        composed.alpha_composite(
            seal,
            (target_x - center, target_y - center),
        )
    return composed


def map_scene_point_to_camera(
    point: Tuple[float, float],
    *,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
) -> Tuple[int, int]:
    eased = 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, progress)))
    zoom_start = 1.04
    zoom_end = 1.08 + min(max(motion_strength, 1), 8) * 0.01
    zoom = zoom_start + (zoom_end - zoom_start) * eased
    scaled_width = int(math.ceil(width * zoom))
    scaled_height = int(math.ceil(height * zoom))
    x_offset = int(max(0, scaled_width - width) * eased)
    y_offset = int(max(0, scaled_height - height) * (1.0 - eased) * 0.5)
    return (
        round(point[0] * zoom - x_offset),
        round(point[1] * zoom - y_offset),
    )


def composite_story_action_effects(
    camera_frame,
    stage: Optional[Dict[str, Any]],
    *,
    action_name: Optional[str],
    action_progress: float,
    character_box: Tuple[int, int, int, int],
    feet_center: Tuple[int, int],
    camera_progress: float,
    motion_strength: int,
    Image,
    ImageDraw,
    ImageFilter,
):
    if stage is None:
        return camera_frame

    state = story_stage_state(action_name, action_progress)
    target = map_scene_point_to_camera(
        stage["target"],
        width=camera_frame.width,
        height=camera_frame.height,
        progress=camera_progress,
        motion_strength=max(1, motion_strength // 2),
    )
    result = camera_frame

    landing_strength = state["landing_strength"]
    if landing_strength > 0.0:
        dust = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(dust)
        feet_x, feet_y = feet_center
        spread = round(result.width * (0.025 + 0.04 * landing_strength))
        alpha = round(125 * landing_strength)
        for offset, size in ((-1.0, 0.55), (-0.4, 0.8), (0.5, 0.72), (1.0, 0.5)):
            center_x = feet_x + round(spread * offset)
            radius_x = max(3, round(spread * size))
            radius_y = max(2, round(radius_x * 0.34))
            draw.ellipse(
                (
                    center_x - radius_x,
                    feet_y - radius_y,
                    center_x + radius_x,
                    feet_y + radius_y,
                ),
                fill=(208, 186, 145, alpha),
            )
        dust = dust.filter(ImageFilter.GaussianBlur(max(1, round(spread * 0.08))))
        result.alpha_composite(dust)

    beam_strength = state["beam_strength"]
    if beam_strength > 0.02:
        character_x, character_y, character_width, character_height = character_box
        cast_hand = (
            character_x + round(character_width * 0.55),
            character_y + round(character_height * 0.4),
        )
        beam = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(beam)
        glow_width = max(4, round(result.width * 0.018 * beam_strength))
        draw.line(
            (cast_hand, target),
            fill=(65, 205, 255, round(150 * beam_strength)),
            width=glow_width * 3,
        )
        beam = beam.filter(ImageFilter.GaussianBlur(max(2, glow_width)))
        result.alpha_composite(beam)
        core = Image.new("RGBA", result.size, (0, 0, 0, 0))
        core_draw = ImageDraw.Draw(core)
        core_draw.line(
            (cast_hand, target),
            fill=(210, 250, 255, round(235 * beam_strength)),
            width=max(2, glow_width),
        )
        result.alpha_composite(core)

    success_afterglow = state["success_strength"] * (
        1.0 - _smoothstep((action_progress - 0.82) / 0.12)
    )
    burst_strength = max(state["impact_strength"], success_afterglow * 0.82)
    if burst_strength > 0.02:
        burst = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)
        radius = max(8, round(result.width * (0.028 + 0.072 * burst_strength)))
        alpha = round(220 * min(1.0, burst_strength))
        flash_radius = max(5, round(radius * 0.52))
        draw.ellipse(
            (
                target[0] - flash_radius,
                target[1] - flash_radius,
                target[0] + flash_radius,
                target[1] + flash_radius,
            ),
            fill=(235, 252, 255, round(185 * min(1.0, burst_strength))),
        )
        draw.ellipse(
            (
                target[0] - radius,
                target[1] - radius,
                target[0] + radius,
                target[1] + radius,
            ),
            outline=(115, 225, 255, alpha),
            width=max(2, round(radius * 0.12)),
        )
        for index in range(8):
            angle = math.tau * index / 8.0
            distance = radius * (1.1 + 0.5 * state["success_strength"])
            spark_x = target[0] + round(math.cos(angle) * distance)
            spark_y = target[1] + round(math.sin(angle) * distance)
            spark_radius = max(1, round(radius * 0.08))
            draw.ellipse(
                (
                    spark_x - spark_radius,
                    spark_y - spark_radius,
                    spark_x + spark_radius,
                    spark_y + spark_radius,
                ),
                fill=(255, 230, 100, alpha),
            )
        result.alpha_composite(burst)
    return result
