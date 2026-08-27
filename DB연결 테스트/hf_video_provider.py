import asyncio
import io
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from hf_media_common import HfMediaError
from motion_policy import SOLO_ANIMATION_ACTIONS, is_solo_action_semantics
from scene_contract import apply_scene_contract, normalize_scene_contract


LOCAL_VIDEO_PROVIDER = (os.getenv("VIDEO_PROVIDER") or "local-animation").strip()
LOCAL_VIDEO_MODEL = (
    os.getenv("LOCAL_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "storybook-motion-sheet-action-v4"
).strip()
LOCAL_VIDEO_FRAME_RATE = int(os.getenv("LOCAL_VIDEO_FRAME_RATE", "30"))
LOCAL_VIDEO_DURATION_SECONDS = float(os.getenv("LOCAL_VIDEO_DURATION_SECONDS", "6.0"))
LOCAL_VIDEO_MAX_DURATION_SECONDS = min(
    max(float(os.getenv("LOCAL_VIDEO_MAX_DURATION_SECONDS", "15.0")), 1.0),
    15.0,
)
LOCAL_VIDEO_DEFAULT_WIDTH = int(os.getenv("LOCAL_VIDEO_DEFAULT_WIDTH", "960"))
LOCAL_VIDEO_DEFAULT_HEIGHT = int(os.getenv("LOCAL_VIDEO_DEFAULT_HEIGHT", "480"))
LOCAL_VIDEO_RENDER_SCALE = min(
    max(int(os.getenv("LOCAL_VIDEO_RENDER_SCALE", "3")), 1),
    3,
)
LOCAL_VIDEO_ENCODER_CRF = min(
    max(int(os.getenv("LOCAL_VIDEO_ENCODER_CRF", "16")), 12),
    28,
)
LOCAL_VIDEO_ENCODER_PRESET = (
    os.getenv("LOCAL_VIDEO_ENCODER_PRESET", "medium").strip() or "medium"
)
LOCAL_VIDEO_FINAL_SHARPNESS = min(
    max(float(os.getenv("LOCAL_VIDEO_FINAL_SHARPNESS", "1.08")), 1.0),
    1.5,
)
JOURNEY_PAN_START = float(os.getenv("LOCAL_VIDEO_JOURNEY_PAN_START", "0.04"))
JOURNEY_PAN_END = float(os.getenv("LOCAL_VIDEO_JOURNEY_PAN_END", "0.62"))
RUN_CHARACTER_SCALE_START = float(
    os.getenv("LOCAL_VIDEO_RUN_SCALE_START", "0.48")
)
RUN_CHARACTER_SCALE_END = float(
    os.getenv("LOCAL_VIDEO_RUN_SCALE_END", "0.30")
)
RUN_CYCLE_BOB_SCALE = float(os.getenv("LOCAL_VIDEO_RUN_BOB_SCALE", "0.004"))
RUN_CYCLE_CONTACT_MIN = min(
    max(float(os.getenv("LOCAL_VIDEO_RUN_CONTACT_MIN", "0.30")), 0.0),
    1.0,
)
TARGET_JOURNEY_STAGE_WIDTH_SCALE = 1.48
TARGET_JOURNEY_STAGE_HEIGHT_SCALE = 1.10
BACKGROUND_JOURNEY_ROUTES = {
    "fantasy_castle": (
        (0.51, 0.95),
        (0.58, 0.88),
        (0.64, 0.80),
        (0.69, 0.71),
        (0.74, 0.61),
        (0.79, 0.49),
    ),
    "adventure_ruins": (
        (0.11, 0.91),
        (0.28, 0.84),
        (0.44, 0.76),
        (0.58, 0.67),
        (0.72, 0.55),
    ),
    "nature_pond": (
        (0.10, 0.91),
        (0.27, 0.84),
        (0.43, 0.77),
        (0.61, 0.66),
        (0.75, 0.54),
    ),
    "friendship_square": (
        (0.12, 0.91),
        (0.28, 0.88),
        (0.44, 0.84),
        (0.58, 0.80),
        (0.70, 0.62),
    ),
    "mystery_library": (
        (0.15, 0.91),
        (0.31, 0.86),
        (0.47, 0.79),
        (0.61, 0.70),
        (0.75, 0.56),
    ),
    "fantasy_crystal_cave": (
        (0.16, 0.93),
        (0.31, 0.85),
        (0.47, 0.75),
        (0.62, 0.62),
        (0.76, 0.45),
    ),
    "adventure_harbor": (
        (0.14, 0.92),
        (0.30, 0.84),
        (0.46, 0.74),
        (0.61, 0.62),
        (0.75, 0.48),
    ),
    "nature_snowfield": (
        (0.16, 0.93),
        (0.33, 0.84),
        (0.48, 0.72),
        (0.62, 0.57),
        (0.75, 0.42),
    ),
    "friendship_festival": (
        (0.18, 0.92),
        (0.35, 0.86),
        (0.50, 0.80),
        (0.64, 0.68),
        (0.76, 0.50),
    ),
    "mystery_clocktower": (
        (0.16, 0.92),
        (0.33, 0.83),
        (0.48, 0.73),
        (0.62, 0.61),
        (0.75, 0.47),
    ),
}
MOTION_SHEET_COLUMNS = 4
MOTION_SHEET_ROWS = 2
MOTION_SHEET_CELL_COUNT = MOTION_SHEET_COLUMNS * MOTION_SHEET_ROWS
RUN_CYCLE_SHEET_COLUMNS = 4
RUN_CYCLE_SHEET_ROWS = 2
RUN_CYCLE_SHEET_CELL_COUNT = RUN_CYCLE_SHEET_COLUMNS * RUN_CYCLE_SHEET_ROWS
RUN_CYCLE_FRAME_SEQUENCE = tuple(range(RUN_CYCLE_SHEET_CELL_COUNT))
WALK_CYCLE_FRAME_SEQUENCE = (0, 1, 4, 5)
JUMP_CYCLE_FRAME_SEQUENCE = (7, 0, 1, 2, 3, 4, 5, 6, 7)
RUN_CYCLE_CYCLES_PER_SECOND = float(
    os.getenv("LOCAL_VIDEO_RUN_CYCLES_PER_SECOND", "1.0")
)
MOTION_FLOW_MIN_SILHOUETTE_IOU = 0.40
GROUNDED_ACTION_FLOW_MIN_SILHOUETTE_IOU = 0.50
RUN_CYCLE_LEG_LOCK_START = 0.58
RUN_CYCLE_LEG_LOCK_END = 0.72
GROUNDED_ACTION_LEG_LOCK_START = 0.62
GROUNDED_ACTION_LEG_LOCK_END = 0.80
ACTION_SHEET_ACTIONS = {
    "wave", "magic", "battle", "rescue", "investigate", "interaction",
}
# These actions need a dedicated cycle or action sheet to change the body pose
# faithfully. A stable reference pose plus semantic root motion is preferable to
# borrowing an unrelated generic walking, rescue, or talking cell.
REFERENCE_FALLBACK_ACTIONS = {
    "jump", "investigate", "interaction", "sit", "stand",
}
MOTION_PHASE_TIMINGS = {
    "prepare": (0.00, 0.24),
    "act": (0.24, 0.72),
    "recover": (0.72, 1.00),
}
ACTION_ALIGNMENT = {
    "journey": {
        "gaze": "toward_target",
        "body_facing": "toward_target",
        "foot_contact": "alternating_grounded",
    },
    "jump": {
        "gaze": "forward",
        "body_facing": "forward",
        "foot_contact": "grounded_airborne_grounded",
    },
    "investigate": {
        "gaze": "scan_then_focus",
        "body_facing": "mostly_stationary",
        "foot_contact": "both_feet_grounded",
    },
    "wave": {
        "gaze": "toward_greeting_target",
        "body_facing": "stationary_toward_target",
        "foot_contact": "both_feet_grounded",
    },
    "sit": {
        "gaze": "forward",
        "body_facing": "stationary",
        "foot_contact": "both_feet_grounded",
    },
    "stand": {
        "gaze": "forward",
        "body_facing": "stationary",
        "foot_contact": "both_feet_grounded",
    },
}
ACTION_SHEET_TIMELINES = {
    "wave": (
        (0.0, 0), (0.18, 0), (0.26, 1), (0.48, 1),
        (0.56, 0), (0.64, 1), (0.82, 1), (0.90, 0), (1.0, 0),
    ),
    "investigate": (
        (0.0, 0), (0.20, 0), (0.30, 2), (0.78, 2), (0.90, 0), (1.0, 0),
    ),
    "interaction": (
        (0.0, 0), (0.22, 0), (0.32, 3), (0.78, 3), (0.90, 0), (1.0, 0),
    ),
    "rescue": (
        (0.0, 0), (0.20, 0), (0.30, 3), (0.80, 3), (0.91, 0), (1.0, 0),
    ),
    "magic": (
        (0.0, 0), (0.16, 0), (0.25, 4), (0.45, 4),
        (0.54, 5), (0.80, 5), (0.90, 0), (1.0, 0),
    ),
    "battle": (
        (0.0, 0), (0.14, 0), (0.22, 6), (0.38, 6),
        (0.48, 7), (0.64, 7), (0.74, 6), (0.88, 6), (0.94, 0), (1.0, 0),
    ),
}
MOTION_ACTION_CELLS = {
    "idle": 0,
    "magic": 4,
    "battle": 5,
    "rescue": 6,
    "investigate": 7,
    "interaction": 7,
    "conversation": 7,
}
PRIMARY_MOTION_TIMELINES = {
    "idle": ((0.0, 0), (1.0, 0)),
    "magic": (
        (0.0, 0),
        (0.18, 0),
        (0.30, 4),
        (0.76, 4),
        (0.88, 0),
        (1.0, 0),
    ),
    "battle": (
        (0.0, 0),
        (0.16, 0),
        (0.26, 5),
        (0.46, 5),
        (0.56, 0),
        (0.68, 5),
        (0.86, 5),
        (0.94, 0),
        (1.0, 0),
    ),
    "rescue": (
        (0.0, 0),
        (0.20, 0),
        (0.34, 6),
        (0.76, 6),
        (0.90, 0),
        (1.0, 0),
    ),
    "investigate": (
        (0.0, 0),
        (0.18, 0),
        (0.30, 6),
        (0.76, 6),
        (0.88, 0),
        (1.0, 0),
    ),
    "interaction": (
        (0.0, 0),
        (0.20, 0),
        (0.32, 7),
        (0.78, 7),
        (0.90, 0),
        (1.0, 0),
    ),
    "conversation": (
        (0.0, 0),
        (0.16, 7),
        (0.34, 7),
        (0.45, 0),
        (0.58, 7),
        (0.82, 7),
        (1.0, 0),
    ),
    "jump": (
        (0.0, 0),
        (0.30, 0),
        (0.36, 1),
        (0.58, 1),
        (0.66, 1),
        (0.76, 0),
        (1.0, 0),
    ),
    "wave": (
        (0.0, 0),
        (0.12, 7),
        (0.32, 7),
        (0.42, 0),
        (0.52, 7),
        (0.72, 7),
        (0.84, 0),
        (1.0, 0),
    ),
}
SECONDARY_MOTION_TIMELINES = {
    "battle": (
        (0.0, 0),
        (0.24, 0),
        (0.38, 5),
        (0.52, 6),
        (0.72, 6),
        (0.86, 3),
        (1.0, 0),
    ),
    "rescue": (
        (0.0, 0), (0.24, 0), (0.42, 6),
        (0.74, 6), (0.90, 0), (1.0, 0),
    ),
    "conversation": (
        (0.0, 0),
        (0.24, 7),
        (0.42, 7),
        (0.56, 0),
        (0.70, 7),
        (0.88, 7),
        (1.0, 0),
    ),
    "interaction": (
        (0.0, 0), (0.20, 0), (0.38, 6),
        (0.72, 6), (0.88, 0), (1.0, 0),
    ),
}


def get_hf_video_config() -> Dict[str, Any]:
    return {
        "configured": True,
        "video_supported": True,
        "video_provider": LOCAL_VIDEO_PROVIDER,
        "video_model": LOCAL_VIDEO_MODEL,
        "video_task": "image-to-video-layered-action-animation",
        "video_requires_gpu": False,
        "video_requires_external_api": False,
        "video_default_frame_rate": LOCAL_VIDEO_FRAME_RATE,
        "video_default_duration_seconds": LOCAL_VIDEO_DURATION_SECONDS,
        "video_max_duration_seconds": LOCAL_VIDEO_MAX_DURATION_SECONDS,
        "video_default_width": LOCAL_VIDEO_DEFAULT_WIDTH,
        "video_default_height": LOCAL_VIDEO_DEFAULT_HEIGHT,
        "video_default_aspect_ratio": "2:1",
        "video_background_motion": "wide-target-tracking-pan",
        "video_motion_focus_default": "character",
        "video_solo_actions": sorted(SOLO_ANIMATION_ACTIONS),
        "video_animation_modes": [
            "sprite_run_cycle_road_v16_stride_amplified",
            "sprite_walk_cycle_road_v16_slow_stride",
            "motion_sheet_jump_v5",
            "identity_locked_jump_cycle_v23_smoothed",
            "identity_locked_jump_cycle_v28_smoothed",
            "motion_sheet_wave_v5",
            "motion_sheet_magic_v5",
            "motion_sheet_investigate_v6",
            "motion_sheet_sit_v1",
            "motion_sheet_stand_v1",
            "motion_sheet_battle_v6",
            "motion_sheet_rescue_v6",
            "motion_sheet_handoff_v6",
            "identity_locked_action_sheet_v23_grounded_smooth",
            "identity_locked_action_sheet_v28_grounded_smooth",
            "identity_locked_action_cycle_v23_stable_alpha",
            "identity_locked_action_cycle_v28_stable_alpha",
            "cinematic_action_compositor_v29_stable_alpha",
            "target_journey_action_v4",
            "motion_sheet_action_v4",
            "motion_sheet_action",
            "layered_action",
            "camera_fallback",
        ],
        "video_frame_interpolation": "premultiplied-alpha-optical-flow-with-grounded-pose-locks-v3",
        "video_pose_transition": "identity-locked-action-cycle-or-optical-flow-fallback",
        "video_effect_style": "action-anchored-subtle-v6",
        "video_render_scale": LOCAL_VIDEO_RENDER_SCALE,
        "video_encoder": {
            "codec": "libx264",
            "crf": LOCAL_VIDEO_ENCODER_CRF,
            "preset": LOCAL_VIDEO_ENCODER_PRESET,
            "final_sharpness": LOCAL_VIDEO_FINAL_SHARPNESS,
        },
    }


def build_fairytale_video_prompt(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    motion_plan: Optional[Dict[str, Any]] = None,
) -> str:
    scene = " ".join(story_text.split())[:500]
    genre_text = f"{genre} fairytale" if genre else "fairytale"
    age_text = f"for {age} year old children" if age else "for children"
    plan = motion_plan or {}
    motion_prompt = str(plan.get("motion_prompt") or "")
    return (
        "high-resolution storybook character action animation, clean edges, "
        "clear readable movement, coherent silhouette, warm magical mood, "
        "no generated text, stable identity, "
        f"{genre_text}, {age_text}, scene: {scene}"
        + (f", motion direction: {motion_prompt}" if motion_prompt else "")
    )


def _load_video_dependencies():
    try:
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise HfMediaError(
            "Local video generation needs pillow, numpy, imageio, and imageio-ffmpeg. "
            "Run `pip install -r requirements.txt` in the backend folder."
        ) from exc
    return imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def _even_dimension(value: int, minimum: int = 256) -> int:
    normalized = max(minimum, int(value))
    return normalized if normalized % 2 == 0 else normalized - 1


def _normalize_frame_count(num_frames: int, frame_rate: int) -> int:
    requested = max(1, int(num_frames))
    max_frames = max(1, int(round(LOCAL_VIDEO_MAX_DURATION_SECONDS * frame_rate)))
    return min(requested, max_frames)


def _ease_in_out(progress: float) -> float:
    normalized = min(max(float(progress), 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * normalized)


def _action_pulse(progress: float, center: float, half_width: float) -> float:
    distance = abs(float(progress) - center)
    if distance >= half_width:
        return 0.0
    return _ease_in_out(1.0 - distance / half_width)


def _phase_ease(progress: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if progress >= end else 0.0
    return _ease_in_out((float(progress) - start) / (end - start))


def _normalized_tokens(values: Optional[Iterable[Any]]) -> set[str]:
    return {
        " ".join(str(value).strip().lower().replace("_", " ").split())
        for value in (values or [])
        if str(value).strip()
    }


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def build_video_motion_plan(
    *,
    story_text: str,
    scene_action: Optional[str] = None,
    scene_target: Optional[str] = None,
    directionality: Optional[str] = None,
    character_pose: Optional[str] = None,
    action_tags: Optional[Iterable[Any]] = None,
    effect_tags: Optional[Iterable[Any]] = None,
    motion_modifier_tags: Optional[Iterable[Any]] = None,
    required_props: Optional[Iterable[Any]] = None,
    visual_anchor: Optional[str] = None,
    background_key: Optional[str] = None,
    action_semantics: Optional[Dict[str, Any]] = None,
    ensemble_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pick one readable motion arc and sprite sequence for a story scene."""

    text = " ".join(str(story_text or "").lower().split())
    pose = " ".join(str(character_pose or "default").lower().replace("_", " ").split())
    action_set = _normalized_tokens(action_tags)
    effect_set = _normalized_tokens(effect_tags)
    motion_modifier_set = _normalized_tokens(motion_modifier_tags)
    prop_set = _normalized_tokens(required_props)
    semantics = dict(action_semantics or {})

    keyword_sets = {
        "magic": (
            "magic", "spell", "wizard", "sorcer", "wand",
            "\ub9c8\ubc95", "\uc8fc\ubb38", "\ub9c8\ubc95\uc0ac", "\uc9c0\ubc95",
        ),
        "battle": (
            "fight", "battle", "attack", "sword", "defeat", "duel",
            "\uc2f8\uc6b0", "\uc2f8\uc6e0", "\uc804\ud22c", "\ubb3c\ub9ac\uce58", "\uacf5\uaca9",
            "\uaca8\ub204", "\ub300\uacb0", "\uac80", "\ub9de\uc11c",
        ),
        "rescue": (
            "rescue", "save", "help", "protect", "carry",
            "\uad6c\ud558", "\uad6c\ud574", "\uad6c\ucd9c", "\uad6c\uc6d0", "\uc0b4\ub824",
            "\ub3d5", "\ubcf4\ud638", "\uc704\ub85c",
        ),
        "journey": (
            "walk", "walking", "run", "travel", "journey", "move", "approach", "toward",
            "\uac77", "\uac78\uc5b4", "\uac78\uc73c", "\ub2ec\ub9ac", "\ub2ec\ub824", "\ub6f0", "\uc5ec\ud589",
            "\uc774\ub3d9", "\ud5a5\ud558", "\ud5a5\ud574", "\ub2e4\uac00\uac00", "\ub098\uc544\uac00", "\ub5a0\ub09c",
        ),
        "jump": (
            "jump", "jumping", "leap", "leaping", "hop", "vault",
            "\uc810\ud504", "\ub6f0\uc5b4\uc624\ub974", "\ub3c4\uc57d", "\ud6cc\ucc0d", "\ub118\uc5b4\uac00",
        ),
        "investigate": (
            "look", "search", "find", "inspect", "explore", "clue", "discover",
            "\ucc3e", "\uc0b4\ud53c", "\ud0d0\ud5d8", "\ubc1c\uacac", "\uc870\uc0ac",
        ),
        "interaction": (
            "open", "close", "take", "receive", "hold", "turn", "push", "pull",
            "\uc5f4", "\ub2eb", "\ubc1b", "\uac74\ub124", "\uc7a1", "\uc950", "\ub3cc\ub824",
            "\ubc00", "\ub2f9\uae30", "\uc9c0\ud53c", "\ucc44\uc6b0",
        ),
        "conversation": (
            "talk", "speak", "tell", "conversation",
            "\ub9d0\ud558", "\ub9d0\ud588", "\ub300\ud654", "\uc774\uc57c\uae30",
        ),
        "wave": (
            "wave", "waving", "greet", "greeting", "goodbye",
            "\uc190\uc744 \ud754\ub4e4", "\uc190\ud754\ub4e4", "\uc778\uc0ac\ud558", "\uc791\ubcc4 \uc778\uc0ac",
        ),
        "sit": (
            "sit", "sits", "sitting", "sat", "\uc549", "\uc549\ub2e4", "\uc549\uc544",
        ),
        "stand": (
            "stand", "stands", "standing", "stood", "\uc77c\uc5b4\ub098", "\uc77c\uc5b4\uc11c",
        ),
    }
    tag_actions = {
        "casting magic": "magic",
        "magic": "magic",
        "fighting": "battle",
        "battle": "battle",
        "helping": "rescue",
        "rescue": "rescue",
        "walking": "journey",
        "running": "journey",
        "jumping": "jump",
        "jump": "jump",
        "journey": "journey",
        "investigating": "investigate",
        "interacting": "interaction",
        "talking": "conversation",
        "waving": "wave",
        "wave": "wave",
        "sitting": "sit",
        "sit": "sit",
        "standing": "stand",
        "stand": "stand",
        "emoting": "conversation",
    }
    pose_actions = {
        "magic": "magic",
        "angry": "battle",
        "rescue": "rescue",
        "walking": "journey",
        "talking": "conversation",
        "sitting": "sit",
        "standing": "stand",
    }

    scores = {action: 0 for action in keyword_sets}
    for action, keywords in keyword_sets.items():
        if _contains_any(text, keywords):
            scores[action] += 3
    for tag in action_set:
        action = tag_actions.get(tag)
        if action:
            scores[action] += 7
    semantic_action = str(semantics.get("animation_action") or "").strip().lower()
    if semantic_action in scores:
        scores[semantic_action] += 16
    if pose_actions.get(pose):
        # The selected asset is deliberately generated for this action, so it
        # should win over a broad verb that happens to appear in the story.
        scores[pose_actions[pose]] += 12
    if {"glowing light", "whirlwind", "fire"}.intersection(effect_set):
        scores["magic"] += 2

    explicit_action = str(scene_action or "").strip().lower()
    if explicit_action in scores or explicit_action == "idle":
        action = explicit_action
    else:
        action = max(scores, key=scores.get)
        if scores[action] == 0:
            action = "idle"
    if (
        semantics.get("motion_mode") == "environmental"
        and semantic_action == "idle"
        and not action_set
    ):
        action = "idle"

    background_targets = {
        "fantasy_castle": "castle",
        "adventure_ruins": "ruins",
        "nature_pond": "forest",
        "friendship_square": "village",
        "mystery_library": "clue",
        "fantasy_crystal_cave": "portal",
        "adventure_harbor": "ship",
        "nature_snowfield": "refuge",
        "friendship_festival": "pavilion",
        "mystery_clocktower": "clock_door",
    }
    target = scene_target or background_targets.get(str(background_key or ""), "scene")
    if _contains_any(
        text,
        (
            "clocktower", "clock tower", "clock", "gear", "secret door",
            "시계탑", "시계", "톱니바퀴", "기어", "비밀문",
        ),
    ):
        target = "clock_door"
    elif _contains_any(
        text,
        ("crystal cave", "cave", "portal", "수정 동굴", "동굴", "차원문", "마법문"),
    ):
        target = "portal"
    elif _contains_any(
        text,
        ("harbor", "port", "ship", "lighthouse", "항구", "부두", "배", "등대"),
    ):
        target = "ship"
    elif _contains_any(
        text,
        ("snowfield", "snow", "cabin", "refuge", "설원", "눈길", "오두막", "산장"),
    ):
        target = "refuge"
    elif _contains_any(
        text,
        ("festival", "pavilion", "stage", "축제", "정자", "무대"),
    ):
        target = "pavilion"
    elif _contains_any(
        text,
        ("castle", "palace", "tower", "\uc131", "\uad81\uc804", "\ud0d1"),
    ):
        target = "castle"
    elif _contains_any(text, ("forest", "woods", "\uc232", "\uc0b0")):
        target = "forest"
    elif _contains_any(text, ("village", "town", "\ub9c8\uc744")):
        target = "village"
    elif _contains_any(text, ("ruins", "temple", "\uc720\uc801", "\uc0ac\uc6d0")):
        target = "ruins"
    elif _contains_any(
        text,
        ("library", "clue", "door", "\ub3c4\uc11c\uad00", "\ub2e8\uc11c", "\ubb38"),
    ):
        target = "clue"
    if scene_target:
        target = scene_target

    effect_by_action = {
        "magic": ["hand_rune"],
        "battle": ["weapon_arc"],
        "rescue": ["support_halo"],
        "journey": ["grounded_steps"],
        "jump": ["landing_dust"],
        "investigate": ["clue_focus"],
        "interaction": ["object_transfer"],
        "conversation": ["speech_gesture"],
        "wave": ["hand_motion_stroke"],
        "sit": [],
        "stand": [],
        "idle": [],
    }
    asset_preferences = {
        "magic": ("casting-magic", "focused"),
        "battle": ("default", "angry"),
        "rescue": ("rescuing", "brave"),
        "journey": ("walking", "determined"),
        "jump": ("walking", "determined"),
        "investigate": (None, "curious"),
        "interaction": (None, None),
        "conversation": ("talking", "friendly"),
        "wave": ("talking", "friendly"),
        "sit": ("sitting", "calm"),
        "stand": ("standing", "ready"),
        "idle": (None, None),
    }
    preferred_pose, preferred_emotion = asset_preferences[action]
    pace = str(semantics.get("pace") or "").strip().lower()
    if pace not in {"walk", "run", "crawl", "climb"}:
        pace = "run" if "fast agile" in motion_modifier_set or "running" in action_set or _contains_any(
            text,
            (
                "run", "running", "rush", "sprint", "\ub2ec\ub9ac", "\ub2ec\ub824",
                "\ub6f0", "\uc9c8\uc8fc", "\uc11c\ub458",
            ),
        ) else "walk"
    if "slow subtle" in motion_modifier_set:
        pace = "walk"
    motion_style = next(
        (
            style
            for style in (
                "slow subtle", "fast agile", "sudden", "trembling",
                "exhausted", "rolling", "splashing", "smiling", "crying",
                "thinking", "startled", "continuous",
            )
            if style in motion_modifier_set
        ),
        None,
    )
    default_motion_mode = "locomotion" if action == "journey" else "stationary"
    motion_mode = str(semantics.get("motion_mode") or default_motion_mode)
    default_participant_count = 2 if action in {"battle", "rescue"} else 1
    try:
        participant_count = max(
            0,
            int(semantics.get("participant_count", default_participant_count)),
        )
    except (TypeError, ValueError):
        participant_count = default_participant_count
    requires_partner = (
        bool(semantics.get("requires_partner"))
        if semantics
        else action in {"battle", "rescue"}
    )
    requires_object = bool(semantics.get("requires_object", False))
    if not prop_set and requires_object and semantics.get("object_role"):
        prop_set.add(str(semantics["object_role"]).strip().lower().replace(" ", "_"))
    solo_action = is_solo_action_semantics(
        {
            "animation_action": action,
            "motion_mode": motion_mode,
            "participant_count": participant_count,
            "requires_partner": requires_partner,
            "requires_object": requires_object,
        }
    )
    locomotion_kind = pace if action == "journey" else None
    alignment = dict(ACTION_ALIGNMENT.get(action, {
        "gaze": "forward",
        "body_facing": "stable",
        "foot_contact": "grounded",
    }))
    if semantics.get("directionality"):
        alignment["body_facing"] = str(semantics["directionality"])
    phase_timings = {
        phase: {"start": start, "end": end}
        for phase, (start, end) in MOTION_PHASE_TIMINGS.items()
    }
    motion_prompt = (
        f"{action} with prepare, act, and recover phases; "
        f"gaze {alignment['gaze']}; body facing {alignment['body_facing']}; "
        f"{alignment['foot_contact']}"
    )
    ensemble = dict(ensemble_profile or {})
    positive_cues = [
        str(value).strip()
        for value in ensemble.get("positive_cues", [])[:5]
        if str(value).strip()
    ]
    negative_cues = [
        str(value).strip()
        for value in ensemble.get("negative_cues", [])[:5]
        if str(value).strip()
    ]
    if positive_cues:
        motion_prompt += "; visual cues: " + ", ".join(positive_cues)
    if negative_cues:
        motion_prompt += "; avoid: " + ", ".join(negative_cues)
    return {
        "action": action,
        "target": target,
        "background_key": str(background_key or ""),
        "pace": pace,
        "locomotion_kind": locomotion_kind,
        "character_pose": pose,
        "effects": effect_by_action[action],
        "preferred_asset_pose": preferred_pose,
        "preferred_asset_emotion": preferred_emotion,
        "source_action_tags": sorted(action_set),
        "source_effect_tags": sorted(effect_set),
        "source_motion_modifier_tags": sorted(motion_modifier_set),
        "motion_style": motion_style,
        "motion_mode": motion_mode,
        "participant_count": participant_count,
        "participant_scope": semantics.get("participant_scope"),
        "requires_partner": requires_partner,
        "requires_object": requires_object,
        "required_props": sorted(prop_set),
        "visual_anchor": str(visual_anchor or semantics.get("visual_anchor") or "").strip()[:240] or None,
        "solo_action": solo_action,
        "phase_timings": phase_timings,
        "motion_phases": ("prepare", "act", "recover"),
        "alignment": alignment,
        "motion_prompt": motion_prompt,
        "ensemble_profile": ensemble,
        "object_role": semantics.get("object_role"),
        "requires_target": bool(semantics.get("requires_target", False)),
        "target_type": semantics.get("target_type"),
        "body_focus": semantics.get("body_focus"),
        "path_pattern": semantics.get("path_pattern"),
        "temporal_pattern": semantics.get("temporal_pattern") or (
            "sudden"
            if {"sudden", "startled"}.intersection(motion_modifier_set)
            else "continuous"
            if "continuous" in motion_modifier_set
            else None
        ),
        "directionality": directionality or semantics.get("directionality"),
        "interaction_kind": semantics.get("interaction_kind"),
        "subject_role": semantics.get("subject_role"),
        "partner_role": semantics.get("partner_role"),
        "semantic_source_word": semantics.get("source_word"),
    }


def _render_frame(
    *,
    source_image,
    Image,
    ImageEnhance,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
    motion_plan: Dict[str, Any],
):
    """Camera-only fallback for an image that has no separate character layer."""

    eased = _ease_in_out(progress)
    action = motion_plan.get("action")
    target = motion_plan.get("target")
    zoom_start = 1.04
    zoom_end = 1.08 + min(max(motion_strength, 1), 8) * 0.01
    if action in {"magic", "battle"}:
        zoom_end += 0.04
    zoom = zoom_start + (zoom_end - zoom_start) * eased
    scaled_width = int(math.ceil(width * zoom))
    scaled_height = int(math.ceil(height * zoom))

    fitted = ImageOps.fit(
        source_image,
        (scaled_width, scaled_height),
        method=getattr(Image, "Resampling", Image).LANCZOS,
        centering=(0.5, 0.5),
    )
    max_x = max(0, scaled_width - width)
    max_y = max(0, scaled_height - height)
    if target == "castle":
        x_offset = int(max_x * (0.25 + 0.75 * eased))
        y_offset = int(max_y * (0.65 - 0.55 * eased))
    else:
        x_offset = int(max_x * eased)
        y_offset = int(max_y * (1.0 - eased) * 0.5)
    frame = fitted.crop((x_offset, y_offset, x_offset + width, y_offset + height))

    interaction_kind = str(motion_plan.get("interaction_kind") or "")
    if interaction_kind == "weather_clearing":
        fog_alpha = int(round(120 * (1.0 - eased)))
        fog = Image.new("RGBA", frame.size, (224, 233, 237, fog_alpha))
        frame = Image.alpha_composite(frame.convert("RGBA"), fog).convert("RGB")
        frame = ImageEnhance.Contrast(frame).enhance(0.78 + 0.24 * eased)

    fade = min(1.0, progress * 6.0, (1.0 - progress) * 6.0)
    brightness = 0.94 + 0.06 * fade
    frame = ImageEnhance.Brightness(frame).enhance(brightness)
    return ImageEnhance.Contrast(frame).enhance(1.02)


def _background_stage_spec(
    width: int,
    height: int,
    motion_plan: Dict[str, Any],
) -> Dict[str, float]:
    action = str(motion_plan.get("action") or "idle")
    target = str(motion_plan.get("target") or "scene")
    if action == "journey" and target != "scene":
        return {
            "width_scale": TARGET_JOURNEY_STAGE_WIDTH_SCALE,
            "height_scale": TARGET_JOURNEY_STAGE_HEIGHT_SCALE,
            "pan_start": min(max(JOURNEY_PAN_START, 0.0), 1.0),
            "pan_end": min(max(JOURNEY_PAN_END, 0.0), 1.0),
        }
    if action == "battle":
        return {
            "width_scale": 1.18,
            "height_scale": 1.12,
            "pan_start": 0.30,
            "pan_end": 0.62,
        }
    if action == "magic":
        return {
            "width_scale": 1.15,
            "height_scale": 1.10,
            "pan_start": 0.38,
            "pan_end": 0.70,
        }
    if action in {"rescue", "interaction"}:
        return {
            "width_scale": 1.12,
            "height_scale": 1.08,
            "pan_start": 0.40,
            "pan_end": 0.58,
        }
    return {
        "width_scale": 1.10 if action == "journey" else 1.06,
        "height_scale": 1.10 if action == "journey" else 1.06,
        "pan_start": 0.50,
        "pan_end": 0.65,
    }


def _background_camera_values(
    width: int,
    height: int,
    progress: float,
    motion_plan: Dict[str, Any],
) -> Dict[str, Any]:
    action = str(motion_plan.get("action") or "idle")
    target = str(motion_plan.get("target") or "scene")
    stage = _background_stage_spec(width, height, motion_plan)
    scaled_width = max(width, int(round(width * stage["width_scale"])))
    scaled_height = max(height, int(round(height * stage["height_scale"])))
    normalized = min(max(float(progress), 0.0), 1.0)
    motion_focus = str(motion_plan.get("motion_focus") or "character")
    follow_strength = 0.42 if motion_focus == "character" else 1.0
    eased = (
        _directed_journey_progress(normalized, motion_plan)
        if action == "journey" and target != "scene"
        else _ease_in_out(normalized)
    )
    max_x = scaled_width - width
    max_y = scaled_height - height
    if action == "journey" and target != "scene":
        x = (
            max_x
            * (stage["pan_start"] + (stage["pan_end"] - stage["pan_start"]) * eased)
        )
        y = max_y * (0.68 - 0.54 * eased)
    elif action == "battle":
        beat = _ease_in_out(min(max((normalized - 0.20) / 0.55, 0.0), 1.0))
        x = max_x * (0.30 + 0.30 * follow_strength * beat)
        y = max_y * (0.64 - 0.12 * follow_strength * beat)
    elif action == "magic":
        cast = _ease_in_out(min(max((normalized - 0.20) / 0.62, 0.0), 1.0))
        x = max_x * (0.34 + 0.34 * follow_strength * cast)
        y = max_y * (0.64 - 0.16 * follow_strength * cast)
    elif action in {"rescue", "interaction"}:
        reach = _ease_in_out(min(max((normalized - 0.18) / 0.56, 0.0), 1.0))
        x = max_x * (0.42 + 0.22 * follow_strength * reach)
        y = max_y * 0.58
    elif action in {"sit", "stand", "wave", "investigate", "conversation"}:
        x = max_x * 0.50
        y = max_y * 0.50
    elif target == "castle":
        x = max_x * (0.15 + 0.75 * eased)
        y = max_y * (0.65 - 0.55 * eased)
    else:
        x = max_x * (0.5 + 0.15 * math.sin(progress * math.pi))
        y = max_y * 0.5
    if action == "battle":
        # Keep the impact readable without a high-frequency camera shake that
        # makes the whole scene look like it is dropping frames.
        impact = _action_pulse(progress, 0.53, 0.11)
        impact_phase = (float(progress) - 0.53) / 0.11
        x += math.sin(impact_phase * math.pi * 2.0) * max_x * 0.035 * impact
        y += math.cos(impact_phase * math.pi * 1.5) * max_y * 0.022 * impact
    x = min(max(x, 0), max_x)
    y = min(max(y, 0), max_y)
    return {
        "stage_width": scaled_width,
        "stage_height": scaled_height,
        "crop_x": x,
        "crop_y": y,
    }


def _prepare_background_stage(
    source_image,
    Image,
    ImageOps,
    width: int,
    height: int,
    motion_plan: Dict[str, Any],
):
    camera = _background_camera_values(
        width,
        height,
        0.0,
        motion_plan,
    )
    return ImageOps.fit(
        source_image.convert("RGBA"),
        (camera["stage_width"], camera["stage_height"]),
        method=getattr(Image, "Resampling", Image).LANCZOS,
        centering=(0.5, 0.5),
    )


def _fit_background(
    source_image,
    Image,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_plan: Dict[str, Any],
    prepared_background=None,
):
    camera = _background_camera_values(
        width,
        height,
        progress,
        motion_plan,
    )
    fitted = prepared_background
    if fitted is None or fitted.size != (
        camera["stage_width"],
        camera["stage_height"],
    ):
        fitted = _prepare_background_stage(
            source_image,
            Image,
            ImageOps,
            width,
            height,
            motion_plan,
        )
    x = camera["crop_x"]
    y = camera["crop_y"]
    return fitted.transform(
        (width, height),
        getattr(Image, "Transform", Image).AFFINE,
        (1.0, 0.0, float(x), 0.0, 1.0, float(y)),
        resample=getattr(Image, "Resampling", Image).BICUBIC,
    )


def _prepare_character(character_image, Image):
    character = character_image.convert("RGBA")
    alpha_bounds = character.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise HfMediaError("Character layer does not contain visible pixels.")
    return character.crop(alpha_bounds)


def _prepare_sprite_sheet(sprite_sheet_image, Image, *, columns: int, rows: int):
    if columns <= 0 or rows <= 0:
        raise HfMediaError("Sprite sheet dimensions must be positive.")
    sheet = sprite_sheet_image.convert("RGBA")
    cells = []
    for row in range(rows):
        top = round(row * sheet.height / rows)
        bottom = round((row + 1) * sheet.height / rows)
        for column in range(columns):
            left = round(column * sheet.width / columns)
            right = round((column + 1) * sheet.width / columns)
            try:
                cell = _prepare_character(
                    sheet.crop((left, top, right, bottom)),
                    Image,
                )
            except HfMediaError as exc:
                raise HfMediaError(
                    f"Sprite sheet cell {len(cells)} does not contain visible pixels."
                ) from exc
            cells.append(cell)
    expected = columns * rows
    if len(cells) != expected:
        raise HfMediaError(f"Sprite sheet must contain exactly {expected} cells.")
    return cells


def _normalize_motion_cells(cells, Image):
    if not cells:
        return []
    canvas_width = max(cell.width for cell in cells)
    canvas_height = max(cell.height for cell in cells)
    normalized_cells = []
    for cell in cells:
        canvas = Image.new(
            "RGBA",
            (canvas_width, canvas_height),
            (0, 0, 0, 0),
        )
        canvas.alpha_composite(
            cell,
            (
                (canvas_width - cell.width) // 2,
                canvas_height - cell.height,
            ),
        )
        normalized_cells.append(canvas)
    return normalized_cells


def _prepare_motion_sheet(motion_sheet_image, Image, *, normalize=True):
    cells = _prepare_sprite_sheet(
        motion_sheet_image,
        Image,
        columns=MOTION_SHEET_COLUMNS,
        rows=MOTION_SHEET_ROWS,
    )
    return _normalize_motion_cells(cells, Image) if normalize else cells


def _prepare_run_cycle_sheet(run_cycle_sheet_image, Image):
    cells = _prepare_sprite_sheet(
        run_cycle_sheet_image,
        Image,
        columns=RUN_CYCLE_SHEET_COLUMNS,
        rows=RUN_CYCLE_SHEET_ROWS,
    )
    return _normalize_motion_cells(cells, Image)


def _select_run_cycle_pose(
    motion_cells,
    *,
    progress: float,
    pace: str,
    duration_seconds: float,
    Image=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    if not motion_cells or len(motion_cells) < RUN_CYCLE_SHEET_CELL_COUNT:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    sequence = (
        RUN_CYCLE_FRAME_SEQUENCE
        if pace == "run"
        else WALK_CYCLE_FRAME_SEQUENCE
    )
    cycles_per_second = RUN_CYCLE_CYCLES_PER_SECOND if pace == "run" else 0.52
    cycle_count = max(1.0, float(duration_seconds) * cycles_per_second)
    frame_position = normalized * cycle_count * len(sequence)
    sequence_index = int(math.floor(frame_position)) % len(sequence)
    next_sequence_index = (sequence_index + 1) % len(sequence)
    first_index = sequence[sequence_index]
    second_index = sequence[next_sequence_index]
    blend = frame_position - math.floor(frame_position)
    if Image is None:
        return motion_cells[first_index if blend < 0.5 else second_index]
    interpolated = _optical_flow_interpolate(
        motion_cells[first_index],
        motion_cells[second_index],
        blend,
        Image=Image,
        cv2=cv2,
        np=np,
        cache=interpolation_cache,
        cache_key=(id(motion_cells), "run", first_index, second_index),
    )
    discrete = (
        motion_cells[first_index]
        if blend < 0.5
        else motion_cells[second_index]
    )
    return _lock_run_cycle_legs(
        interpolated,
        discrete,
        Image,
    )


def _select_jump_cycle_pose(
    motion_cells,
    *,
    progress: float,
    Image=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    if not motion_cells or len(motion_cells) < RUN_CYCLE_SHEET_CELL_COUNT:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    local = min(max((normalized - 0.38) / 0.16, 0.0), 1.0)
    position = local * (len(JUMP_CYCLE_FRAME_SEQUENCE) - 1)
    sequence_index = min(
        int(math.floor(position)),
        len(JUMP_CYCLE_FRAME_SEQUENCE) - 2,
    )
    first_index = JUMP_CYCLE_FRAME_SEQUENCE[sequence_index]
    if local >= 1.0:
        return motion_cells[JUMP_CYCLE_FRAME_SEQUENCE[-1]]
    second_index = JUMP_CYCLE_FRAME_SEQUENCE[sequence_index + 1]
    blend = position - math.floor(position)
    if Image is None:
        return motion_cells[first_index if blend < 0.5 else second_index]
    return _optical_flow_interpolate(
        motion_cells[first_index],
        motion_cells[second_index],
        _ease_in_out(blend),
        Image=Image,
        cv2=cv2,
        np=np,
        cache=interpolation_cache,
        cache_key=(id(motion_cells), "jump", first_index, second_index),
    )


def _select_action_sheet_pose(
    motion_cells,
    *,
    action: str,
    progress: float,
    Image=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    if not motion_cells or len(motion_cells) < MOTION_SHEET_CELL_COUNT:
        return None
    timeline = ACTION_SHEET_TIMELINES.get(action)
    if not timeline:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    for index in range(len(timeline) - 1):
        start_time, first_index = timeline[index]
        end_time, second_index = timeline[index + 1]
        if normalized > end_time:
            continue
        if first_index == second_index or end_time <= start_time:
            return motion_cells[first_index]
        local_progress = (normalized - start_time) / (end_time - start_time)
        if Image is None:
            return motion_cells[first_index if local_progress < 0.5 else second_index]
        interpolated = _optical_flow_interpolate(
            motion_cells[first_index],
            motion_cells[second_index],
            _ease_in_out(local_progress),
            Image=Image,
            cv2=cv2,
            np=np,
            cache=interpolation_cache,
            cache_key=(id(motion_cells), "action-sheet", action, first_index, second_index),
            min_silhouette_iou=GROUNDED_ACTION_FLOW_MIN_SILHOUETTE_IOU,
        )
        discrete = (
            motion_cells[first_index]
            if local_progress < 0.5
            else motion_cells[second_index]
        )
        return _lock_grounded_action_legs(interpolated, discrete, Image)
    return motion_cells[timeline[-1][1]]


def _select_dedicated_action_cycle_pose(
    motion_cells,
    *,
    action: str,
    progress: float,
    Image=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    if not motion_cells or len(motion_cells) < MOTION_SHEET_CELL_COUNT:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    if action == "battle":
        start, end = 0.16, 0.76
    elif action in {"rescue", "interaction"}:
        start, end = 0.14, 0.82
    elif action in {"sit", "stand"}:
        start, end = 0.10, 0.76
    else:
        start, end = 0.14, 0.82
    if normalized <= start:
        return motion_cells[0]
    if normalized >= end:
        return motion_cells[-1]
    local = _ease_in_out((normalized - start) / (end - start))
    position = local * (MOTION_SHEET_CELL_COUNT - 1)
    first_index = min(int(math.floor(position)), MOTION_SHEET_CELL_COUNT - 2)
    second_index = first_index + 1
    blend = position - first_index
    if Image is None:
        return motion_cells[first_index if blend < 0.5 else second_index]
    interpolated = _optical_flow_interpolate(
        motion_cells[first_index],
        motion_cells[second_index],
        _ease_in_out(blend),
        Image=Image,
        cv2=cv2,
        np=np,
        cache=interpolation_cache,
        cache_key=(id(motion_cells), "action-cycle", action, first_index, second_index),
        prefer_single_warp=True,
    )
    discrete = (
        motion_cells[first_index]
        if blend < 0.5
        else motion_cells[second_index]
    )
    if action in {"journey", "sit", "stand"}:
        return interpolated
    return _lock_grounded_action_legs(interpolated, discrete, Image)


def _select_posture_cycle_pose(
    sit_cells,
    stand_cells,
    *,
    action: str,
    progress: float,
    Image=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    if action == "sit":
        if not sit_cells or len(sit_cells) < MOTION_SHEET_CELL_COUNT:
            return None
        sources = {"sit": sit_cells}
        keyframes = (
            (0.00, ("sit", 0)),
            (0.10, ("sit", 0)),
            (0.24, ("sit", 1)),
            (0.39, ("sit", 2)),
            (0.55, ("sit", 3)),
            (0.68, ("sit", 4)),
            (1.00, ("sit", 4)),
        )
    elif action == "stand":
        if not stand_cells or len(stand_cells) < MOTION_SHEET_CELL_COUNT:
            return None
        sources = {"stand": stand_cells}
        if sit_cells and len(sit_cells) >= MOTION_SHEET_CELL_COUNT:
            sources["sit"] = sit_cells
            keyframes = (
                (0.00, ("sit", 4)),
                (0.10, ("sit", 4)),
                (0.24, ("sit", 3)),
                (0.39, ("sit", 2)),
                (0.54, ("sit", 1)),
                (0.68, ("sit", 0)),
                (0.78, ("stand", 7)),
                (1.00, ("stand", 7)),
            )
        else:
            keyframes = (
                (0.00, ("stand", 0)),
                (0.12, ("stand", 0)),
                (0.27, ("stand", 1)),
                (0.43, ("stand", 3)),
                (0.59, ("stand", 5)),
                (0.73, ("stand", 7)),
                (1.00, ("stand", 7)),
            )
    else:
        return None

    normalized = min(max(float(progress), 0.0), 1.0)
    for (start_time, first), (end_time, second) in zip(keyframes, keyframes[1:]):
        if normalized > end_time:
            continue
        first_cell = sources[first[0]][first[1]]
        if first == second or end_time <= start_time:
            return first_cell
        second_cell = sources[second[0]][second[1]]
        local = (normalized - start_time) / (end_time - start_time)
        if Image is None:
            return first_cell if local < 0.5 else second_cell
        return _optical_flow_interpolate(
            first_cell,
            second_cell,
            _ease_in_out(local),
            Image=Image,
            cv2=cv2,
            np=np,
            cache=interpolation_cache,
            cache_key=(id(sit_cells), id(stand_cells), action, first, second),
            prefer_single_warp=True,
        )
    final_source, final_index = keyframes[-1][1]
    return sources[final_source][final_index]


def _blend_bottom_aligned(first, second, amount: float, Image):
    blend = min(max(float(amount), 0.0), 1.0)
    if blend <= 0.0:
        return first
    if blend >= 1.0:
        return second
    width = max(first.width, second.width)
    height = max(first.height, second.height)

    def on_canvas(source):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(
            source,
            ((width - source.width) // 2, height - source.height),
        )
        return canvas

    return Image.blend(on_canvas(first), on_canvas(second), blend)


def _bottom_aligned_canvases(first, second, Image):
    width = max(first.width, second.width)
    height = max(first.height, second.height)

    def on_canvas(source):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(
            source,
            ((width - source.width) // 2, height - source.height),
        )
        return canvas

    return on_canvas(first), on_canvas(second)


def _optical_flow_interpolate(
    first,
    second,
    amount: float,
    *,
    Image,
    cv2,
    np,
    cache: Optional[Dict[Any, Any]],
    cache_key: Any,
    min_silhouette_iou: float = MOTION_FLOW_MIN_SILHOUETTE_IOU,
    prefer_single_warp: bool = False,
):
    blend = min(max(float(amount), 0.0), 1.0)
    if blend <= 0.015:
        return first
    if blend >= 0.985:
        return second
    if cv2 is None or np is None:
        if prefer_single_warp:
            return first if blend < 0.5 else second
        return _blend_bottom_aligned(first, second, blend, Image)

    flow_cache = cache if cache is not None else {}
    prepared_key = (cache_key, bool(prefer_single_warp))
    prepared = flow_cache.get(prepared_key)
    if prepared is None:
        first_canvas, second_canvas = _bottom_aligned_canvases(first, second, Image)
        first_rgba = np.asarray(first_canvas, dtype=np.uint8)
        second_rgba = np.asarray(second_canvas, dtype=np.uint8)

        def gray_for_flow(rgba):
            alpha = rgba[..., 3:4].astype(np.float32) / 255.0
            rgb = rgba[..., :3].astype(np.float32)
            composite = rgb * alpha + 127.0 * (1.0 - alpha)
            return cv2.cvtColor(
                composite.astype(np.uint8),
                cv2.COLOR_RGB2GRAY,
            )

        first_gray = gray_for_flow(first_rgba)
        second_gray = gray_for_flow(second_rgba)
        first_mask = first_rgba[..., 3] >= 64
        second_mask = second_rgba[..., 3] >= 64
        union = np.logical_or(first_mask, second_mask).sum()
        silhouette_iou = (
            float(np.logical_and(first_mask, second_mask).sum()) / float(union)
            if union
            else 0.0
        )
        if silhouette_iou < min_silhouette_iou:
            prepared = ("pose_cut", silhouette_iou)
            flow_cache[prepared_key] = prepared
        else:
            flow_args = (0.5, 4, 25, 4, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
            forward = cv2.calcOpticalFlowFarneback(
                first_gray,
                second_gray,
                None,
                *flow_args,
            )
            backward = cv2.calcOpticalFlowFarneback(
                second_gray,
                first_gray,
                None,
                *flow_args,
            )
            grid_x, grid_y = np.meshgrid(
                np.arange(first_canvas.width),
                np.arange(first_canvas.height),
            )

            def premultiply(rgba):
                normalized = rgba.astype(np.float32) / 255.0
                alpha = normalized[..., 3:4]
                return np.concatenate(
                    (normalized[..., :3] * alpha, alpha),
                    axis=2,
                )

            prepared = (
                "single_warp" if prefer_single_warp else "optical_flow",
                premultiply(first_rgba),
                premultiply(second_rgba),
                forward,
                backward,
                grid_x,
                grid_y,
            )
            flow_cache[prepared_key] = prepared
    if prepared[0] == "pose_cut":
        return first if blend < 0.5 else second

    mode, first_rgba, second_rgba, forward, backward, grid_x, grid_y = prepared

    def warp(source, flow, scale):
        map_x = (grid_x - flow[..., 0] * scale).astype(np.float32)
        map_y = (grid_y - flow[..., 1] * scale).astype(np.float32)
        return cv2.remap(
            source,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

    def unpremultiply(premultiplied):
        alpha = np.clip(premultiplied[..., 3:4], 0.0, 1.0)
        rgb = np.zeros_like(premultiplied[..., :3], dtype=np.float32)
        np.divide(
            premultiplied[..., :3],
            np.maximum(alpha, 1.0 / 255.0),
            out=rgb,
            where=alpha > (1.0 / 255.0),
        )
        rgba = np.concatenate((np.clip(rgb, 0.0, 1.0), alpha), axis=2)
        rgba[alpha[..., 0] <= (1.0 / 255.0)] = 0.0
        return Image.fromarray(
            np.rint(rgba * 255.0).astype(np.uint8),
            "RGBA",
        )

    if mode == "single_warp":
        if blend < 0.5:
            dominant = warp(first_rgba, forward, blend)
        else:
            dominant = warp(second_rgba, backward, 1.0 - blend)
        dominant[..., 3] = np.where(
            dominant[..., 3] >= (10.0 / 255.0),
            dominant[..., 3],
            0.0,
        )
        return unpremultiply(dominant)
    warped_first = warp(first_rgba, forward, blend)
    warped_second = warp(second_rgba, backward, 1.0 - blend)
    premultiplied = np.clip(
        warped_first * (1.0 - blend) + warped_second * blend,
        0.0,
        1.0,
    )
    return unpremultiply(premultiplied)


def _lock_lower_body(
    interpolated,
    discrete,
    Image,
    *,
    start_ratio: float,
    end_ratio: float,
):
    interpolated_canvas, discrete_canvas = _bottom_aligned_canvases(
        interpolated,
        discrete,
        Image,
    )
    height = interpolated_canvas.height
    start = max(0, min(height - 1, round(height * start_ratio)))
    end = max(start + 1, min(height, round(height * end_ratio)))
    span = max(end - start, 1)
    mask_column = Image.new("L", (1, height), 0)
    mask_column.putdata(
        [
            0
            if y < start
            else 255
            if y >= end
            else round(255 * (y - start) / span)
            for y in range(height)
        ]
    )
    mask = mask_column.resize((interpolated_canvas.width, height))
    # Run-cycle cells are normalized to one shared canvas. Keeping that canvas
    # prevents each pose from being cropped and rescaled independently.
    return Image.composite(discrete_canvas, interpolated_canvas, mask)


def _lock_run_cycle_legs(interpolated, discrete, Image):
    """Keep articulated legs crisp while allowing the upper body to interpolate."""
    return _lock_lower_body(
        interpolated,
        discrete,
        Image,
        start_ratio=RUN_CYCLE_LEG_LOCK_START,
        end_ratio=RUN_CYCLE_LEG_LOCK_END,
    )


def _lock_grounded_action_legs(interpolated, discrete, Image):
    """Smooth upper-body action while retaining a readable grounded stance."""
    return _lock_lower_body(
        interpolated,
        discrete,
        Image,
        start_ratio=GROUNDED_ACTION_LEG_LOCK_START,
        end_ratio=GROUNDED_ACTION_LEG_LOCK_END,
    )


def _motion_timeline(
    action: str,
    pace: str,
    role: str,
    target_facing: bool = False,
    interaction_kind: Optional[str] = None,
):
    if interaction_kind == "aim":
        if role == "secondary":
            return PRIMARY_MOTION_TIMELINES["idle"]
        return (
            (0.0, 0),
            (0.18, 5),
            (0.82, 5),
            (1.0, 0),
        )
    if action == "journey":
        if target_facing:
            sequence = (
                RUN_CYCLE_FRAME_SEQUENCE
                if pace == "run"
                else (0, 1, 2, 3, 2, 1)
            )
            steps = 20 if pace == "run" else 14
            return tuple(
                (
                    index / max(steps - 1, 1),
                    sequence[index % len(sequence)],
                )
                for index in range(steps)
            )
        sequence = (1, 2) if pace not in {"crawl", "climb"} else (0, 1, 2, 1)
        steps = 16 if pace == "run" else 12
        timeline = [(0.0, 0)]
        for index in range(steps):
            time = 0.06 + (0.88 * index / max(steps - 1, 1))
            timeline.append((time, sequence[index % len(sequence)]))
        timeline.append((1.0, 0))
        return tuple(timeline)
    if action == "sit":
        return (
            (0.00, 0), (0.20, 0), (0.48, 6),
            (0.72, 6), (1.00, 6),
        )
    if action == "stand":
        return (
            (0.00, 6), (0.28, 6), (0.58, 0),
            (0.82, 0), (1.00, 0),
        )
    if role == "secondary" and action in SECONDARY_MOTION_TIMELINES:
        return SECONDARY_MOTION_TIMELINES[action]
    return PRIMARY_MOTION_TIMELINES.get(action, PRIMARY_MOTION_TIMELINES["idle"])


def _select_motion_pose(
    motion_cells,
    *,
    motion_plan: Dict[str, Any],
    progress: float,
    Image,
    role: str = "primary",
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
    target_facing: bool = False,
):
    if not motion_cells or len(motion_cells) < MOTION_SHEET_CELL_COUNT:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    action = str(motion_plan.get("action") or "idle")
    timeline = _motion_timeline(
        action,
        str(motion_plan.get("pace") or "walk"),
        role,
        target_facing,
        interaction_kind=str(motion_plan.get("interaction_kind") or ""),
    )
    for index in range(len(timeline) - 1):
        start_time, first_index = timeline[index]
        end_time, second_index = timeline[index + 1]
        if normalized > end_time:
            continue
        if first_index == second_index or end_time <= start_time:
            return motion_cells[first_index]
        local_progress = (normalized - start_time) / (end_time - start_time)
        interpolated = _optical_flow_interpolate(
            motion_cells[first_index],
            motion_cells[second_index],
            _ease_in_out(local_progress),
            Image=Image,
            cv2=cv2,
            np=np,
            cache=interpolation_cache,
            cache_key=(id(motion_cells), first_index, second_index),
            min_silhouette_iou=(
                GROUNDED_ACTION_FLOW_MIN_SILHOUETTE_IOU
                if action != "journey"
                else MOTION_FLOW_MIN_SILHOUETTE_IOU
            ),
        )
        if action in {
            "magic", "battle", "rescue", "investigate",
            "interaction", "conversation", "wave", "sit", "stand",
        }:
            discrete = (
                motion_cells[first_index]
                if local_progress < 0.5
                else motion_cells[second_index]
            )
            return _lock_grounded_action_legs(interpolated, discrete, Image)
        return interpolated
    return motion_cells[timeline[-1][1]]


def _sample_background_route(
    background_key: str,
    progress: float,
) -> Optional[tuple[float, float]]:
    points = BACKGROUND_JOURNEY_ROUTES.get(str(background_key or ""))
    if not points:
        return None
    normalized = min(max(float(progress), 0.0), 1.0)
    position = normalized * (len(points) - 1)
    index = min(int(math.floor(position)), len(points) - 2)
    local = position - index
    p0 = points[max(index - 1, 0)]
    p1 = points[index]
    p2 = points[index + 1]
    p3 = points[min(index + 2, len(points) - 1)]

    def catmull_rom(axis: int) -> float:
        value = 0.5 * (
            2.0 * p1[axis]
            + (-p0[axis] + p2[axis]) * local
            + (2.0 * p0[axis] - 5.0 * p1[axis] + 4.0 * p2[axis] - p3[axis])
            * local**2
            + (-p0[axis] + 3.0 * p1[axis] - 3.0 * p2[axis] + p3[axis])
            * local**3
        )
        return min(max(value, 0.0), 1.0)

    return catmull_rom(0), catmull_rom(1)


def _directed_journey_progress(
    progress: float,
    motion_plan: Optional[Dict[str, Any]],
) -> float:
    normalized = min(max(float(progress), 0.0), 1.0)
    direction = str((motion_plan or {}).get("directionality") or "").lower()
    if direction in {"right_to_left", "reverse"}:
        return 1.0 - normalized
    return normalized


def _journey_route_screen_position(
    *,
    progress: float,
    width: int,
    height: int,
    motion_plan: Dict[str, Any],
) -> Optional[tuple[float, float]]:
    route = _sample_background_route(
        str(motion_plan.get("background_key") or ""),
        _directed_journey_progress(progress, motion_plan),
    )
    if route is None:
        return None
    camera = _background_camera_values(
        width,
        height,
        progress,
        motion_plan,
    )
    center_x = route[0] * camera["stage_width"] - camera["crop_x"]
    ground_y = route[1] * camera["stage_height"] - camera["crop_y"]
    return (
        min(max(center_x, width * 0.08), width * 0.92),
        min(max(ground_y, height * 0.38), height * 0.96),
    )


def _character_motion_values(
    *,
    action: str,
    progress: float,
    width: int,
    height: int,
    motion_strength: int,
    motion_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    normalized = min(max(float(progress), 0.0), 1.0)
    eased = _ease_in_out(normalized)
    strength = min(max(int(motion_strength), 1), 8) / 8.0
    bob = 0.0
    ground_contact = 1.0
    rotation = 0.0
    if action == "journey":
        journey_progress = _directed_journey_progress(progress, motion_plan)
        journey_eased = _ease_in_out(journey_progress)
        scale = RUN_CHARACTER_SCALE_START + (
            RUN_CHARACTER_SCALE_END - RUN_CHARACTER_SCALE_START
        ) * journey_progress
        route_position = (
            _journey_route_screen_position(
                progress=progress,
                width=width,
                height=height,
                motion_plan=motion_plan,
            )
            if motion_plan
            else None
        )
        if route_position is None:
            center_x = width * (0.16 + 0.47 * journey_eased)
            ground_y = height * (0.94 - 0.31 * journey_eased)
        else:
            center_x, ground_y = route_position
        pace = str((motion_plan or {}).get("pace") or "walk")
        if (motion_plan or {}).get("path_pattern") == "erratic":
            center_x += math.sin(progress * math.pi * 7) * width * 0.025
            ground_y += math.sin(progress * math.pi * 5) * height * 0.015
        bob = 0.0
        rotation = 0.0
        if pace == "crawl":
            scale = 0.39 - 0.045 * journey_progress
            ground_y += height * 0.045
            crawl_phase = journey_progress * math.pi * 6.0
            bob = -abs(math.sin(crawl_phase)) * height * 0.006
            rotation = math.sin(crawl_phase) * 1.4
        elif pace == "climb":
            scale = 0.46 - 0.10 * journey_progress
            climb_phase = journey_progress * math.pi * 5.0
            bob = -abs(math.sin(climb_phase)) * height * 0.010
            rotation = math.sin(climb_phase) * 2.0
        elif pace == "run":
            duration = float((motion_plan or {}).get("_duration_seconds") or 8.0)
            cycle_progress = _directed_journey_progress(progress, motion_plan)
            cycle_phase = (
                cycle_progress * duration * RUN_CYCLE_CYCLES_PER_SECOND
            ) % 1.0
            bob = -abs(math.sin(cycle_phase * math.pi * 2.0)) * height * RUN_CYCLE_BOB_SCALE
            contact_phase = 0.5 + 0.5 * math.cos(cycle_phase * math.pi * 4.0)
            ground_contact = RUN_CYCLE_CONTACT_MIN + (
                1.0 - RUN_CYCLE_CONTACT_MIN
            ) * contact_phase
    elif action == "jump":
        jump_progress = min(max((normalized - 0.38) / 0.16, 0.0), 1.0)
        airborne = math.sin(jump_progress * math.pi)
        landing = _action_pulse(progress, 0.55, 0.035)
        scale = 0.60 + airborne * 0.018 - landing * 0.008
        center_x = width * (0.45 + _ease_in_out(jump_progress) * 0.10)
        ground_y = height * 0.94
        bob = -airborne * height * 0.28 + landing * height * 0.008
        rotation = math.sin(jump_progress * math.pi * 2.0) * 2.2 * airborne
        ground_contact = 1.0 - airborne
    elif action == "sit":
        lower = _phase_ease(normalized, 0.20, 0.46)
        settle = _phase_ease(normalized, 0.68, 0.86)
        scale = 0.60 - lower * 0.045 + settle * 0.008
        center_x = width * 0.50
        ground_y = height * (0.94 + lower * 0.025)
        bob = -settle * height * 0.004
        rotation = lower * 1.5 - settle * 0.8
    elif action == "stand":
        rise = _phase_ease(normalized, 0.20, 0.58)
        settle = _phase_ease(normalized, 0.68, 0.88)
        scale = 0.55 + rise * 0.05 - settle * 0.004
        center_x = width * 0.50
        ground_y = height * (0.965 - rise * 0.025)
        bob = -rise * height * 0.004 + settle * height * 0.002
        rotation = -rise * 1.3 + settle * 0.7
    elif action == "battle":
        if (motion_plan or {}).get("interaction_kind") == "aim":
            hold = _action_pulse(progress, 0.55, 0.48)
            scale = 0.59 + hold * 0.018
            center_x = width * 0.42
            ground_y = height * 0.94
            bob = -hold * height * 0.006
            rotation = -hold * 0.7
        else:
            preparation = _phase_ease(normalized, 0.22, 0.36)
            strike = _phase_ease(normalized, 0.36, 0.56)
            recovery = _phase_ease(normalized, 0.56, 0.78)
            impact = _action_pulse(progress, 0.53, 0.10)
            root_step = 0.035 * preparation + 0.16 * strike - 0.045 * recovery
            scale = 0.585 + impact * 0.035 - recovery * 0.008
            center_x = width * (0.34 + root_step)
            ground_y = height * 0.94
            bob = -(0.45 * preparation + 0.80 * strike) * height * 0.010
            rotation = -preparation * 1.2 - strike * 3.8 + recovery * 1.7
    elif action == "magic":
        gather = _phase_ease(normalized, 0.18, 0.38)
        release = _phase_ease(normalized, 0.40, 0.64)
        settle = _phase_ease(normalized, 0.64, 0.84)
        cast = _action_pulse(progress, 0.53, 0.38)
        pulse = math.sin(progress * math.pi * 8) * cast
        root_step = -0.025 * gather + 0.12 * release + 0.025 * settle
        scale = 0.60 + cast * 0.025 + pulse * 0.006
        center_x = width * (0.44 + root_step)
        ground_y = height * 0.94
        bob = -(0.35 * gather + 0.60 * release) * height * 0.008 + pulse * height * 0.006
        rotation = -gather * 1.0 - release * 2.0 + settle * 1.0 + pulse * 0.7
    elif action == "rescue":
        approach = _phase_ease(normalized, 0.14, 0.46)
        contact = _action_pulse(progress, 0.54, 0.34)
        recover = _phase_ease(normalized, 0.70, 0.90)
        scale = 0.595 + contact * 0.028
        center_x = width * (0.38 + 0.10 * approach - 0.02 * recover)
        ground_y = height * 0.94 + contact * height * 0.006
        bob = -approach * height * 0.006 - contact * height * 0.008
        rotation = approach * 0.8 + contact * 1.8 - recover * 0.8
    elif action == "investigate":
        inspect = _phase_ease(normalized, 0.18, 0.42)
        recover = _phase_ease(normalized, 0.68, 0.90)
        focus = _action_pulse(progress, 0.54, 0.38)
        scan = math.sin(progress * math.pi * 2.0) * focus
        scale = 0.60 + focus * 0.018
        center_x = width * (0.47 + 0.035 * inspect - 0.018 * recover)
        ground_y = height * 0.94
        bob = -focus * height * 0.004
        rotation = inspect * 0.7 - recover * 0.4 + scan * 0.45
    elif action == "interaction":
        approach = _phase_ease(normalized, 0.14, 0.46)
        contact = _action_pulse(progress, 0.54, 0.34)
        recover = _phase_ease(normalized, 0.70, 0.90)
        scale = 0.60 + contact * 0.022
        center_x = width * (0.38 + 0.10 * approach - 0.02 * recover)
        ground_y = height * 0.94
        bob = -approach * height * 0.005 - contact * height * 0.006
        rotation = approach * 0.6 + contact * 1.2 - recover * 0.6
    elif action == "conversation":
        pulse = math.sin(progress * math.pi * 4)
        scale = 0.60 + pulse * 0.012
        center_x = width * 0.50
        ground_y = height * 0.94
        bob = pulse * height * 0.008
        rotation = pulse * 0.7
    elif action == "wave":
        gesture = math.sin(progress * math.pi * 6)
        lift = _phase_ease(normalized, 0.10, 0.26)
        lower = _phase_ease(normalized, 0.76, 0.92)
        envelope = lift * (1.0 - lower)
        scale = 0.60 + envelope * 0.005
        center_x = width * 0.50
        ground_y = height * 0.94
        bob = gesture * envelope * height * 0.0015
        rotation = gesture * envelope * 0.55
    elif str((motion_plan or {}).get("interaction_kind") or "") == "stop":
        settle = _phase_ease(normalized, 0.05, 0.52)
        scale = 0.60
        center_x = width * (0.50 - 0.018 * (1.0 - settle))
        ground_y = height * 0.94
        bob = -_action_pulse(progress, 0.18, 0.12) * height * 0.010
        rotation = -_action_pulse(progress, 0.18, 0.12) * 2.0
    elif str((motion_plan or {}).get("interaction_kind") or "") == "turn_in_place":
        turn = _phase_ease(normalized, 0.16, 0.76)
        scale = 0.60
        center_x = width * 0.50
        ground_y = height * 0.94
        bob = -math.sin(turn * math.pi) * height * 0.006
        rotation = math.sin(turn * math.pi) * 10.0
    else:
        pulse = math.sin(progress * math.pi * 2)
        scale = 0.60 + pulse * 0.008
        center_x = width * 0.50
        ground_y = height * 0.94
        bob = pulse * height * 0.005

    modifiers = set((motion_plan or {}).get("source_motion_modifier_tags") or [])
    if "slow subtle" in modifiers:
        bob *= 0.45
        rotation *= 0.45
    if "exhausted" in modifiers:
        bob += math.sin(progress * math.pi * 3) * height * 0.009
        rotation += math.sin(progress * math.pi * 2) * 1.2
    if "trembling" in modifiers:
        center_x += math.sin(progress * math.pi * 24) * width * 0.006
        rotation += math.sin(progress * math.pi * 30) * 1.4
    if "startled" in modifiers:
        recoil = _action_pulse(progress, 0.32, 0.11)
        scale += recoil * 0.025
        ground_y -= recoil * height * 0.025
        rotation -= recoil * 2.2

    return {
        "scale": scale,
        "center_x": center_x,
        "ground_y": ground_y + bob,
        "rotation": rotation,
        "ground_contact": ground_contact,
    }


def _paste_shadow(
    frame,
    Image,
    ImageDraw,
    ImageFilter,
    center_x: float,
    ground_y: float,
    character_width: int,
    character_height: int,
    ground_contact: float = 1.0,
):
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    contact = min(max(float(ground_contact), 0.0), 1.0)
    shadow_width = max(16, int(character_width * (0.52 + contact * 0.18)))
    shadow_height = max(8, int(character_height * (0.045 + contact * 0.015)))
    left = int(center_x - shadow_width / 2)
    top = int(ground_y - shadow_height / 2)
    ImageDraw.Draw(shadow).ellipse(
        (left, top, left + shadow_width, top + shadow_height),
        fill=(26, 29, 48, int(52 + contact * 44)),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, shadow_height // 2)))
    frame.alpha_composite(shadow)


def _apply_reference_motion_transform(character_image, *, action: str, pace: str, progress: float, Image):
    """Give unsupported locomotion/posture verbs a bounded pose change without changing identity."""

    normalized = min(max(float(progress), 0.0), 1.0)
    if action == "journey" and pace == "crawl":
        width_scale, height_scale = 1.16, 0.72
    elif action == "journey" and pace == "climb":
        width_scale, height_scale = 1.04, 0.86
    elif action == "sit":
        amount = _phase_ease(normalized, 0.08, 0.56)
        width_scale = 1.0 + 0.06 * amount
        height_scale = 1.0 - 0.20 * amount
    elif action == "stand":
        amount = 1.0 - _phase_ease(normalized, 0.10, 0.70)
        width_scale = 1.0 + 0.06 * amount
        height_scale = 1.0 - 0.20 * amount
    else:
        return character_image

    target_width = max(8, int(round(character_image.width * width_scale)))
    target_height = max(8, int(round(character_image.height * height_scale)))
    transformed = character_image.resize(
        (target_width, target_height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    canvas = Image.new(
        "RGBA",
        (target_width, character_image.height),
        (0, 0, 0, 0),
    )
    canvas.alpha_composite(
        transformed,
        (0, max(0, character_image.height - target_height)),
    )
    return canvas


def _paste_character_layer(
    *,
    frame,
    character_image,
    Image,
    ImageDraw,
    ImageFilter,
    center_x: float,
    ground_y: float,
    scale: float,
    rotation: float,
    ground_contact: float = 1.0,
):
    target_height = max(12, int(frame.height * scale))
    resize_scale = target_height / character_image.height
    target_width = max(8, int(round(character_image.width * resize_scale)))
    character = character_image.resize(
        (target_width, target_height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    _paste_shadow(
        frame,
        Image,
        ImageDraw,
        ImageFilter,
        center_x,
        ground_y,
        target_width,
        target_height,
        ground_contact,
    )
    rotated = character.rotate(
        rotation,
        resample=getattr(Image, "Resampling", Image).BICUBIC,
        expand=True,
    )
    visible_bounds = rotated.getchannel("A").getbbox()
    if visible_bounds is None:
        return target_width, target_height
    # Motion cells share one normalized canvas. Anchoring that canvas center
    # avoids a left/right wobble when an arm, cape, or leg changes the visible
    # alpha bounds between adjacent poses.
    stable_center_x = rotated.width / 2.0
    x = int(round(center_x - stable_center_x))
    y = int(round(ground_y - visible_bounds[3]))
    frame.alpha_composite(rotated, (x, y))
    return target_width, target_height


def _secondary_motion_values(
    *,
    action: str,
    progress: float,
    width: int,
    height: int,
) -> Dict[str, float]:
    beat = _action_pulse(progress, 0.53, 0.18)
    if action == "battle":
        first_recoil = _phase_ease(progress, 0.48, 0.64)
        first_recovery = _phase_ease(progress, 0.64, 0.76)
        counter_strike = _action_pulse(progress, 0.78, 0.11)
        counter_recovery = _phase_ease(progress, 0.78, 0.94)
        return {
            "scale": 0.53 - beat * 0.025 + counter_strike * 0.012,
            "center_x": width * (
                0.72
                + first_recoil * 0.085
                - first_recovery * 0.025
                - counter_recovery * 0.035
            ),
            "ground_y": height * (
                0.94 - first_recoil * 0.018 - counter_strike * 0.006
            ),
            "rotation": (
                first_recoil * 4.0
                - first_recovery * 1.4
                - counter_strike * 2.4
                + counter_recovery * 1.0
            ),
        }
    if action == "rescue":
        reach = _phase_ease(progress, 0.14, 0.46)
        recover = _phase_ease(progress, 0.70, 0.90)
        return {
            "scale": 0.49 + beat * 0.012,
            "center_x": width * (0.75 - reach * 0.08 + recover * 0.025),
            "ground_y": height * (0.94 + beat * 0.004),
            "rotation": -reach * 1.0 + recover * 0.6,
        }
    if action == "conversation":
        pulse = math.sin(progress * math.pi * 4)
        return {
            "scale": 0.53 + pulse * 0.009,
            "center_x": width * 0.72,
            "ground_y": height * 0.94 + pulse * height * 0.004,
            "rotation": -pulse * 0.6,
        }
    if action == "interaction":
        reach = _phase_ease(progress, 0.14, 0.46)
        recover = _phase_ease(progress, 0.70, 0.90)
        return {
            "scale": 0.50 + beat * 0.015,
            "center_x": width * (0.75 - reach * 0.075 + recover * 0.025),
            "ground_y": height * (0.94 - beat * 0.004),
            "rotation": -reach * 1.1 + recover * 0.8,
        }
    return {
        "scale": 0.50,
        "center_x": width * 0.72,
        "ground_y": height * 0.94,
        "rotation": 0.0,
    }


def _composite_effect_cell(
    *,
    frame,
    cell,
    Image,
    center_x: float,
    center_y: float,
    target_height: int,
    rotation: float = 0.0,
    opacity: float = 1.0,
):
    if cell is None or target_height <= 0:
        return
    scale = target_height / max(cell.height, 1)
    target_width = max(1, int(round(cell.width * scale)))
    effect = cell.resize(
        (target_width, target_height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    if opacity < 0.999:
        alpha = effect.getchannel("A").point(
            lambda value: int(value * min(max(opacity, 0.0), 1.0))
        )
        effect.putalpha(alpha)
    if abs(rotation) > 0.01:
        effect = effect.rotate(
            rotation,
            resample=getattr(Image, "Resampling", Image).BICUBIC,
            expand=True,
        )
    frame.alpha_composite(
        effect,
        (
            int(center_x - effect.width / 2),
            int(center_y - effect.height / 2),
        ),
    )


def _draw_atlas_action_effects(
    *,
    frame,
    effect_cells,
    Image,
    action: str,
    progress: float,
    center_x: float,
    ground_y: float,
    character_width: int,
    character_height: int,
    interaction_kind: Optional[str] = None,
):
    def cell(index: int):
        return effect_cells[index] if len(effect_cells) > index else None

    def place(
        index: int,
        x: float,
        y: float,
        size: float,
        *,
        rotation: float = 0.0,
        opacity: float = 1.0,
    ):
        _composite_effect_cell(
            frame=frame,
            cell=cell(index),
            Image=Image,
            center_x=x,
            center_y=y,
            target_height=max(1, int(size)),
            rotation=rotation,
            opacity=opacity,
        )

    if action == "journey":
        step_phase = (progress * 8.0) % 1.0
        place(
            0,
            center_x - character_width * (0.16 + step_phase * 0.14),
            ground_y - character_height * 0.015,
            character_height * 0.18,
            opacity=max(0.0, 1.0 - step_phase * 1.35),
        )
        return
    if action == "jump":
        landing = _action_pulse(progress, 0.55, 0.06)
        if landing > 0.01:
            place(
                7,
                center_x,
                ground_y - character_height * 0.015,
                character_height * (0.24 + landing * 0.08),
                opacity=landing,
            )
        return
    if action == "magic":
        hand_x = center_x + character_width * 0.20
        hand_y = ground_y - character_height * 0.72
        gather = _action_pulse(progress, 0.36, 0.22)
        if gather > 0.01:
            place(
                3,
                hand_x,
                hand_y,
                character_height * (0.24 + gather * 0.08),
                rotation=math.sin(progress * math.pi * 8) * 4.0,
                opacity=gather,
            )
        release = min(max((progress - 0.44) / 0.25, 0.0), 1.0)
        if release > 0.0:
            travel = _ease_in_out(release)
            target_x = frame.width * 0.82
            target_y = frame.height * 0.38
            orb_x = hand_x + (target_x - hand_x) * travel
            orb_y = hand_y + (target_y - hand_y) * travel - math.sin(travel * math.pi) * frame.height * 0.08
            place(
                4,
                orb_x,
                orb_y,
                character_height * 0.14,
                rotation=-10.0,
                opacity=min(1.0, release * 1.4),
            )
            impact = _action_pulse(progress, 0.73, 0.075)
            if impact > 0.01:
                place(
                    2,
                    target_x,
                    target_y,
                    character_height * (0.20 + impact * 0.12),
                    opacity=impact,
                )
        return
    if action == "battle":
        swing = _action_pulse(progress, 0.48, 0.17)
        if swing > 0.01:
            place(
                1,
                center_x + character_width * 0.38,
                ground_y - character_height * 0.52,
                character_height * 0.19,
                rotation=-10.0,
                opacity=swing,
            )
        impact = _action_pulse(progress, 0.53, 0.075)
        if impact > 0.01:
            target_x = frame.width * 0.68
            target_y = ground_y - character_height * 0.50
            place(
                2,
                target_x,
                target_y,
                character_height * (0.17 + impact * 0.13),
                opacity=impact,
            )
            place(
                0,
                center_x,
                ground_y - character_height * 0.01,
                character_height * 0.15,
                opacity=impact * 0.75,
            )
        return
    if action == "rescue":
        reach = _action_pulse(progress, 0.52, 0.35)
        if reach > 0.01:
            place(
                5,
                center_x + character_width * 0.30,
                ground_y - character_height * 0.42,
                character_height * (0.24 + reach * 0.08),
                rotation=-4.0,
                opacity=reach,
            )
        return
    if action == "interaction" and interaction_kind == "handoff_receive":
        transfer = _ease_in_out(min(max((progress - 0.22) / 0.48, 0.0), 1.0))
        item_x = frame.width * (0.635 - 0.075 * transfer)
        item_y = ground_y - character_height * 0.42
        sparkle = _action_pulse(progress, 0.56, 0.28)
        if sparkle > 0.01:
            place(
                6,
                item_x,
                item_y,
                character_height * 0.11,
                opacity=sparkle,
            )


def _semantic_prop_kind(motion_plan: Dict[str, Any], action: str) -> Optional[str]:
    """Choose a restrained prop silhouette that makes the action legible."""

    values = [
        motion_plan.get("target"),
        motion_plan.get("target_type"),
        motion_plan.get("object_role"),
        motion_plan.get("visual_anchor"),
        *(motion_plan.get("required_props") or []),
    ]
    text = " ".join(
        str(value or "").strip().lower().replace("_", " ")
        for value in values
    )
    if action == "journey" and motion_plan.get("pace") == "climb":
        return "climb_rope"
    if action == "journey" and motion_plan.get("pace") == "crawl":
        return "crawl_trail"
    if any(token in text for token in ("chest", "treasure", "상자", "보물")):
        return "chest"
    if any(token in text for token in ("key", "열쇠")):
        return "key"
    if any(token in text for token in ("book", "clue", "scroll", "책", "단서", "두루마리")):
        return "book"
    if any(token in text for token in ("door", "문", "gate", "문")):
        return "door"
    if action == "jump":
        return "stone"
    if action == "investigate":
        return "clue"
    if action == "interaction":
        return "object"
    return None


def _draw_semantic_prop(
    *,
    frame,
    Image,
    ImageDraw,
    ImageFilter,
    action: str,
    progress: float,
    motion_plan: Dict[str, Any],
    center_x: float,
    ground_y: float,
    character_width: int,
    character_height: int,
):
    """Draw one stable, readable prop instead of relying on particle effects."""

    kind = _semantic_prop_kind(motion_plan, action)
    if kind is None or action not in {"journey", "jump", "investigate", "interaction"}:
        return
    normalized = min(max(float(progress), 0.0), 1.0)
    if action == "journey" and kind == "climb_rope":
        visibility = 0.84
        prop_x = center_x + character_width * 0.40
        prop_ground = ground_y
    elif action == "journey" and kind == "crawl_trail":
        visibility = 0.64
        prop_x = center_x - character_width * 0.24
        prop_ground = ground_y + character_height * 0.01
    elif action == "jump":
        visibility = _phase_ease(normalized, 0.10, 0.20) * (
            1.0 - _phase_ease(normalized, 0.84, 0.94)
        )
        prop_x = frame.width * 0.58
        prop_ground = ground_y
    elif action == "investigate":
        visibility = 0.72 + 0.18 * _action_pulse(normalized, 0.54, 0.40)
        prop_x = min(frame.width * 0.76, frame.width * 0.68)
        prop_ground = ground_y - character_height * 0.06
    else:
        visibility = _phase_ease(normalized, 0.10, 0.28) * (
            1.0 - _phase_ease(normalized, 0.78, 0.94)
        )
        if kind in {"chest", "door"}:
            prop_x = frame.width * 0.62
            prop_ground = ground_y
        elif motion_plan.get("interaction_kind") == "handoff_receive":
            prop_x = frame.width * 0.635 - frame.width * 0.075 * _ease_in_out(
                min(max((normalized - 0.20) / 0.62, 0.0), 1.0)
            )
        else:
            prop_x = center_x + character_width * 0.34
        prop_ground = ground_y - character_height * 0.40
    if visibility <= 0.01:
        return

    size = max(
        14,
        int(
            character_height
            * (
                0.28
                if kind in {"chest", "door"}
                else 0.34
                if kind in {"book", "clue"}
                else 0.22
                if action == "jump"
                else 0.18
            )
        ),
    )
    glow_kind = kind in {"key", "clue"} or "glow" in " ".join(
        str(value or "").lower() for value in (motion_plan.get("required_props") or [])
    )
    if glow_kind:
        glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_radius = size * 0.72
        glow_draw.ellipse(
            (
                prop_x - glow_radius,
                prop_ground - size * 0.46 - glow_radius,
                prop_x + glow_radius,
                prop_ground - size * 0.46 + glow_radius,
            ),
            fill=(255, 218, 118, int(42 * visibility)),
        )
        frame.alpha_composite(
            glow.filter(ImageFilter.GaussianBlur(max(2, size // 5)))
        )

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = int(220 * visibility)
    left = prop_x - size * 0.50
    top = prop_ground - size
    if kind == "climb_rope":
        rope_top = prop_ground - character_height * 1.05
        draw.line(
            (prop_x, rope_top, prop_x, prop_ground),
            fill=(218, 181, 112, alpha),
            width=max(2, size // 12),
        )
        for knot_index in range(3):
            knot_y = rope_top + (prop_ground - rope_top) * (0.24 + knot_index * 0.27)
            draw.ellipse(
                (
                    prop_x - size * 0.10,
                    knot_y - size * 0.10,
                    prop_x + size * 0.10,
                    knot_y + size * 0.10,
                ),
                fill=(247, 211, 138, alpha),
            )
    elif kind == "crawl_trail":
        draw.arc(
            (
                prop_x - size * 0.66,
                prop_ground - size * 0.22,
                prop_x + size * 0.66,
                prop_ground + size * 0.08,
            ),
            8,
            172,
            fill=(220, 196, 163, alpha),
            width=max(1, size // 15),
        )
    elif action == "jump" or kind == "stone":
        draw.ellipse(
            (left, top + size * 0.25, prop_x + size * 0.50, prop_ground),
            fill=(85, 98, 122, alpha),
            outline=(207, 221, 236, alpha),
            width=max(1, size // 18),
        )
        draw.line(
            (left + size * 0.23, top + size * 0.46, prop_x, top + size * 0.30),
            fill=(239, 247, 255, int(alpha * 0.72)),
            width=max(1, size // 24),
        )
    elif kind == "chest":
        draw.rounded_rectangle(
            (left, top + size * 0.30, prop_x + size * 0.50, prop_ground),
            radius=max(2, size // 9),
            fill=(142, 83, 44, alpha),
            outline=(255, 213, 125, alpha),
            width=max(1, size // 18),
        )
        draw.arc(
            (left, top, prop_x + size * 0.50, top + size * 0.72),
            180,
            360,
            fill=(255, 213, 125, alpha),
            width=max(1, size // 18),
        )
        draw.line(
            (prop_x, top + size * 0.34, prop_x, prop_ground - size * 0.03),
            fill=(255, 232, 153, alpha),
            width=max(1, size // 16),
        )
    elif kind == "key":
        shaft_y = top + size * 0.48
        draw.ellipse(
            (left + size * 0.08, shaft_y - size * 0.18, left + size * 0.42, shaft_y + size * 0.18),
            outline=(255, 230, 136, alpha),
            width=max(1, size // 14),
        )
        draw.line(
            (left + size * 0.35, shaft_y, prop_x + size * 0.48, shaft_y),
            fill=(255, 230, 136, alpha),
            width=max(1, size // 12),
        )
        draw.line(
            (prop_x + size * 0.25, shaft_y, prop_x + size * 0.25, shaft_y + size * 0.18),
            fill=(255, 230, 136, alpha),
            width=max(1, size // 14),
        )
    elif kind in {"book", "clue"}:
        draw.polygon(
            (
                (left, top + size * 0.20),
                (prop_x, top + size * 0.34),
                (prop_x, prop_ground - size * 0.06),
                (left, prop_ground - size * 0.20),
            ),
            fill=(73, 112, 164, alpha),
            outline=(245, 243, 190, alpha),
        )
        draw.line(
            (prop_x, top + size * 0.34, prop_x, prop_ground - size * 0.06),
            fill=(255, 241, 176, alpha),
            width=max(1, size // 18),
        )
        draw.line(
            (left + size * 0.13, top + size * 0.43, left + size * 0.38, top + size * 0.49),
            fill=(235, 245, 255, int(alpha * 0.72)),
            width=max(1, size // 20),
        )
    elif kind == "door":
        draw.rounded_rectangle(
            (left, top, prop_x + size * 0.50, prop_ground),
            radius=max(2, size // 12),
            fill=(77, 62, 96, alpha),
            outline=(241, 206, 128, alpha),
            width=max(1, size // 18),
        )
        draw.ellipse(
            (prop_x + size * 0.19, top + size * 0.52, prop_x + size * 0.29, top + size * 0.62),
            fill=(255, 231, 155, alpha),
        )
    else:
        draw.rounded_rectangle(
            (left, top + size * 0.20, prop_x + size * 0.50, prop_ground),
            radius=max(2, size // 9),
            fill=(76, 119, 145, alpha),
            outline=(220, 242, 242, alpha),
            width=max(1, size // 18),
        )
    frame.alpha_composite(overlay)


def _draw_action_effects(
    *,
    frame,
    Image,
    ImageDraw,
    ImageFilter,
    action: str,
    progress: float,
    center_x: float,
    ground_y: float,
    character_width: int,
    character_height: int,
    interaction_kind: Optional[str] = None,
    effect_cells=None,
    suppress_effects: bool = False,
):
    # Dedicated action sheets should be readable without decorative overlays.
    # Keep the default v29 effect behavior unchanged for existing callers.
    if suppress_effects:
        return
    if effect_cells and action in {
        "journey", "jump", "magic", "battle", "rescue", "interaction",
    }:
        _draw_atlas_action_effects(
            frame=frame,
            effect_cells=effect_cells,
            Image=Image,
            action=action,
            progress=progress,
            center_x=center_x,
            ground_y=ground_y,
            character_width=character_width,
            character_height=character_height,
            interaction_kind=interaction_kind,
        )
        return
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    phase = progress * math.pi * 2
    if action == "journey":
        step_phase = (progress * 10.0) % 1.0
        for index in range(2):
            local = (step_phase + index * 0.50) % 1.0
            fade = max(0.0, 1.0 - local * 1.45)
            if fade <= 0.0:
                continue
            side = -1.0 if index == 0 else 1.0
            x = center_x - character_width * (0.12 + local * 0.16)
            y = ground_y - character_height * 0.012 + side * character_height * 0.008
            half_width = max(3, int(character_height * 0.016))
            half_height = max(2, int(character_height * 0.006))
            draw.arc(
                (x - half_width, y - half_height, x + half_width, y + half_height),
                start=8,
                end=172,
                fill=(205, 180, 143, int(95 * fade)),
                width=max(1, int(character_height * 0.005)),
            )
    elif action == "jump":
        takeoff = _action_pulse(progress, 0.38, 0.030)
        landing = _action_pulse(progress, 0.55, 0.035)
        impact = max(takeoff * 0.55, landing)
        if impact > 0.01:
            dust = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            dust_draw = ImageDraw.Draw(dust)
            for index in range(4):
                direction = -1.0 if index < 2 else 1.0
                spread = character_width * (0.10 + (index % 2) * 0.10) * impact
                x = center_x + direction * spread
                y = ground_y - character_height * 0.012
                radius = max(3, int(character_height * (0.015 + (index % 2) * 0.006)))
                dust_draw.ellipse(
                    (x - radius, y - radius / 2, x + radius, y + radius / 2),
                    fill=(225, 202, 166, int(105 * impact)),
                )
            overlay.alpha_composite(
                dust.filter(ImageFilter.GaussianBlur(max(1, int(character_height * 0.006))))
            )
    elif action == "magic":
        cast = _action_pulse(progress, 0.53, 0.43)
        if cast <= 0.01:
            return
        hand_x = center_x + character_width * 0.20
        hand_y = ground_y - character_height * 0.72
        aura_radius = character_height * cast * (0.15 + 0.025 * math.sin(phase * 4))
        aura = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        aura_draw = ImageDraw.Draw(aura)
        aura_draw.ellipse(
            (hand_x - aura_radius, hand_y - aura_radius, hand_x + aura_radius, hand_y + aura_radius),
            fill=(138, 226, 255, int(80 * cast)),
        )
        overlay.alpha_composite(aura.filter(ImageFilter.GaussianBlur(max(4, int(aura_radius * 0.32)))))
        draw = ImageDraw.Draw(overlay)
        for index in range(4):
            angle = phase * 0.55 + index * math.pi / 2
            radius = aura_radius * (0.72 + (index % 2) * 0.12)
            x = hand_x + math.cos(angle) * radius
            y = hand_y + math.sin(angle) * radius
            dot = max(1, int(character_height * 0.008))
            draw.line(
                (x - dot * 1.8, y, x + dot * 1.8, y),
                fill=(255, 246, 174, int(210 * cast)),
                width=max(1, dot),
            )
            draw.line(
                (x, y - dot * 1.8, x, y + dot * 1.8),
                fill=(255, 246, 174, int(210 * cast)),
                width=max(1, dot),
            )
        ring = aura_radius * 0.74
        draw.ellipse((hand_x - ring, hand_y - ring, hand_x + ring, hand_y + ring), outline=(189, 246, 255, 195), width=max(2, int(character_height * 0.012)))
    elif action == "battle":
        if interaction_kind == "aim":
            aim_strength = 0.55 + 0.15 * math.sin(phase)
            hand_x = center_x + character_width * 0.20
            hand_y = ground_y - character_height * 0.60
            target_x = frame.width * 0.76
            target_y = frame.height * 0.43
            radius = max(12, int(frame.height * 0.055))
            draw.line(
                (hand_x, hand_y, target_x, target_y),
                fill=(255, 231, 139, int(105 * aim_strength)),
                width=max(2, int(frame.height * 0.005)),
            )
            draw.ellipse(
                (
                    target_x - radius,
                    target_y - radius,
                    target_x + radius,
                    target_y + radius,
                ),
                outline=(255, 236, 164, int(220 * aim_strength)),
                width=max(2, int(frame.height * 0.007)),
            )
            cross = radius * 1.35
            draw.line(
                (target_x - cross, target_y, target_x + cross, target_y),
                fill=(255, 244, 201, 205),
                width=max(2, int(frame.height * 0.004)),
            )
            draw.line(
                (target_x, target_y - cross, target_x, target_y + cross),
                fill=(255, 244, 201, 205),
                width=max(2, int(frame.height * 0.004)),
            )
        else:
            strike = _action_pulse(progress, 0.53, 0.12)
            if strike <= 0.01:
                return
            arc_box = (
                center_x + character_width * 0.10,
                ground_y - character_height * 0.78,
                center_x + character_width * 0.92,
                ground_y - character_height * 0.08,
            )
            start = 215 - int(42 * strike)
            draw.arc(arc_box, start=start, end=start + 88, fill=(255, 235, 157, int(210 * strike)), width=max(3, int(character_height * 0.018)))
            impact_x = center_x + character_width * 0.78
            impact_y = ground_y - character_height * 0.47
            for ray in range(4):
                angle = math.pi / 4 + ray * math.pi / 2
                inner = character_height * 0.035
                outer = character_height * (0.07 + 0.035 * strike)
                draw.line(
                    (
                        impact_x + math.cos(angle) * inner,
                        impact_y + math.sin(angle) * inner,
                        impact_x + math.cos(angle) * outer,
                        impact_y + math.sin(angle) * outer,
                    ),
                    fill=(255, 247, 205, int(205 * strike)),
                    width=max(2, int(character_height * 0.009)),
                )
    elif action == "rescue":
        glow_x = center_x + character_width * 0.30
        glow_y = ground_y - character_height * 0.36
        radius = character_height * (0.14 + 0.015 * math.sin(phase))
        glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse(
            (glow_x - radius, glow_y - radius, glow_x + radius, glow_y + radius),
            fill=(255, 224, 160, 48),
        )
        overlay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(5, int(radius * 0.50)))))
        draw = ImageDraw.Draw(overlay)
        draw.arc(
            (glow_x - radius, glow_y - radius, glow_x + radius, glow_y + radius),
            start=205,
            end=335,
            fill=(255, 236, 191, 155),
            width=max(2, int(character_height * 0.008)),
        )
    elif action == "investigate":
        focus_x = center_x + character_width * 0.54
        focus_y = ground_y - character_height * 0.76
        radius = character_height * 0.052
        corner = radius * 0.42
        focus = _action_pulse(progress, 0.54, 0.38)
        if focus <= 0.01:
            return
        color = (255, 239, 172, int(145 * focus))
        width_px = max(2, int(character_height * 0.007))
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x = focus_x + sx * radius
            y = focus_y + sy * radius
            draw.line((x, y, x - sx * corner, y), fill=color, width=width_px)
            draw.line((x, y, x, y - sy * corner), fill=color, width=width_px)
    elif action == "interaction":
        reach = _action_pulse(progress, 0.52, 0.44)
        hand_y = ground_y - character_height * 0.42
        if interaction_kind == "handoff_receive":
            transfer = _ease_in_out(
                min(max((progress - 0.20) / 0.62, 0.0), 1.0)
            )
            item_x = frame.width * (0.635 - 0.075 * transfer)
            item_y = hand_y - character_height * 0.015
            glow_radius = max(8, int(character_height * (0.042 + reach * 0.010)))
            glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.ellipse(
                (
                    item_x - glow_radius * 1.5,
                    item_y - glow_radius * 1.5,
                    item_x + glow_radius * 1.5,
                    item_y + glow_radius * 1.5,
                ),
                fill=(255, 218, 130, int(38 + 42 * reach)),
            )
            overlay.alpha_composite(
                glow.filter(ImageFilter.GaussianBlur(max(3, glow_radius)))
            )
            draw = ImageDraw.Draw(overlay)
            item_width = max(12, int(character_height * 0.075))
            item_height = max(8, int(character_height * 0.042))
            line_width = max(2, int(character_height * 0.009))
            draw.rounded_rectangle(
                (
                    item_x - item_width / 2,
                    item_y - item_height / 2,
                    item_x + item_width / 2,
                    item_y + item_height / 2,
                ),
                radius=max(2, int(item_height * 0.28)),
                fill=(255, 224, 146, 220),
                outline=(255, 245, 208, 245),
                width=line_width,
            )
        else:
            hand_x = center_x + character_width * 0.28
            radius = character_height * (0.045 + reach * 0.035)
            draw.ellipse(
                (hand_x - radius, hand_y - radius, hand_x + radius, hand_y + radius),
                outline=(255, 232, 166, int(90 + 120 * reach)),
                width=max(2, int(character_height * 0.010)),
            )
    elif action == "conversation":
        gesture = math.sin(progress * math.pi * 4) ** 2
        hand_x = center_x + character_width * 0.25
        hand_y = ground_y - character_height * 0.63
        radius = character_height * 0.07
        draw.arc(
            (hand_x - radius, hand_y - radius, hand_x + radius, hand_y + radius),
            start=300,
            end=45,
            fill=(255, 242, 198, int(135 * gesture)),
            width=max(2, int(character_height * 0.007)),
        )
        face_x = center_x + character_width * 0.04
        face_y = ground_y - character_height * 0.87
        for dot_index in range(3):
            dot_alpha = int((80 + dot_index * 35) * gesture)
            dot_radius = max(2, int(character_height * (0.012 + dot_index * 0.004)))
            dot_x = face_x + dot_index * character_width * 0.10
            dot_y = face_y - dot_index * character_height * 0.045
            draw.ellipse(
                (
                    dot_x - dot_radius,
                    dot_y - dot_radius,
                    dot_x + dot_radius,
                    dot_y + dot_radius,
                ),
                fill=(250, 239, 191, dot_alpha),
            )
    elif action == "wave":
        envelope = math.sin(progress * math.pi) ** 2
        hand_x = center_x + character_width * 0.29
        hand_y = ground_y - character_height * 0.76
        radius = character_height * (0.085 + envelope * 0.012)
        for index in range(2):
            inset = index * character_height * 0.025
            draw.arc(
                (
                    hand_x - radius - inset,
                    hand_y - radius - inset,
                    hand_x + radius + inset,
                    hand_y + radius + inset,
                ),
                start=285,
                end=75,
                fill=(255, 242, 190, int((155 - index * 40) * envelope)),
                width=max(2, int(character_height * 0.007)),
            )
    frame.alpha_composite(overlay)


def _render_layered_frame(
    *,
    background_image,
    prepared_background=None,
    character_image,
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
    motion_plan: Dict[str, Any],
    secondary_character_image=None,
    character_motion_cells=None,
    character_target_journey_motion_cells=None,
    character_run_cycle_motion_cells=None,
    character_jump_cycle_motion_cells=None,
    character_action_motion_cells=None,
    character_battle_cycle_motion_cells=None,
    character_magic_cycle_motion_cells=None,
    character_interaction_cycle_motion_cells=None,
    character_sit_cycle_motion_cells=None,
    character_stand_cycle_motion_cells=None,
    character_crawl_cycle_motion_cells=None,
    character_climb_cycle_motion_cells=None,
    action_fx_motion_cells=None,
    suppress_action_effects: bool = False,
    secondary_character_motion_cells=None,
    cv2=None,
    np=None,
    interpolation_cache: Optional[Dict[Any, Any]] = None,
):
    frame = _fit_background(
        background_image,
        Image,
        ImageOps,
        width,
        height,
        progress,
        motion_plan,
        prepared_background=prepared_background,
    )
    values = _character_motion_values(
        action=str(motion_plan.get("action") or "idle"),
        progress=progress,
        width=width,
        height=height,
        motion_strength=motion_strength,
        motion_plan=motion_plan,
    )
    action = str(motion_plan.get("action") or "idle")
    journey_pace = str(motion_plan.get("pace") or "walk")
    target_facing = bool(
        (character_run_cycle_motion_cells or character_target_journey_motion_cells)
        and action == "journey"
        and journey_pace in {"walk", "run"}
        and str(motion_plan.get("target") or "scene") != "scene"
    )
    use_run_cycle = bool(
        character_run_cycle_motion_cells
        and action == "journey"
        and journey_pace in {"walk", "run"}
    )
    use_jump_cycle = bool(character_jump_cycle_motion_cells and action == "jump")
    use_action_sheet = bool(
        character_action_motion_cells and action in ACTION_SHEET_ACTIONS
    )
    dedicated_action_cells = (
        character_battle_cycle_motion_cells
        if action == "battle"
        else character_magic_cycle_motion_cells
        if action == "magic"
        else character_interaction_cycle_motion_cells
        if action in {"rescue", "interaction"}
        else character_sit_cycle_motion_cells
        if action == "sit"
        else character_stand_cycle_motion_cells
        if action == "stand"
        else None
    )
    dedicated_travel_cells = (
        character_crawl_cycle_motion_cells
        if action == "journey" and str(motion_plan.get("pace") or "") == "crawl"
        else character_climb_cycle_motion_cells
        if action == "journey" and str(motion_plan.get("pace") or "") == "climb"
        else None
    )
    use_posture_cycle = bool(
        action in {"sit", "stand"}
        and (
            character_sit_cycle_motion_cells
            or character_stand_cycle_motion_cells
        )
    )
    if use_jump_cycle:
        rendered_character = _select_jump_cycle_pose(
            character_jump_cycle_motion_cells,
            progress=progress,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif use_run_cycle:
        rendered_character = _select_run_cycle_pose(
            character_run_cycle_motion_cells,
            progress=progress,
            pace=str(motion_plan.get("pace") or "walk"),
            duration_seconds=float(motion_plan.get("_duration_seconds") or 8.0),
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif use_posture_cycle:
        rendered_character = _select_posture_cycle_pose(
            character_sit_cycle_motion_cells,
            character_stand_cycle_motion_cells,
            action=action,
            progress=progress,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif dedicated_travel_cells:
        rendered_character = _select_dedicated_action_cycle_pose(
            dedicated_travel_cells,
            action="journey",
            progress=progress,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif dedicated_action_cells:
        rendered_character = _select_dedicated_action_cycle_pose(
            dedicated_action_cells,
            action=action,
            progress=progress,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif use_action_sheet:
        rendered_character = _select_action_sheet_pose(
            character_action_motion_cells,
            action=action,
            progress=progress,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
        ) or character_image
    elif action in REFERENCE_FALLBACK_ACTIONS:
        rendered_character = character_image
    else:
        active_character_motion_cells = (
            character_target_journey_motion_cells
            if target_facing
            else character_motion_cells
        )
        rendered_character = _select_motion_pose(
            active_character_motion_cells,
            motion_plan=motion_plan,
            progress=progress,
            Image=Image,
            role="primary",
            cv2=cv2,
            np=np,
            interpolation_cache=interpolation_cache,
            target_facing=target_facing,
        ) or character_image
    if (
        action == "journey"
        and journey_pace in {"crawl", "climb"}
        and not dedicated_travel_cells
    ):
        rendered_character = _apply_reference_motion_transform(
            character_image,
            action=action,
            pace=journey_pace,
            progress=progress,
            Image=Image,
        )
    elif action in {"sit", "stand"} and not use_posture_cycle:
        rendered_character = _apply_reference_motion_transform(
            character_image,
            action=action,
            pace="walk",
            progress=progress,
            Image=Image,
        )
    if (
        action == "journey"
        and str(motion_plan.get("directionality") or "").lower()
        in {"right_to_left", "reverse"}
    ):
        rendered_character = ImageOps.mirror(rendered_character)
    estimated_character_height = max(12, int(frame.height * values["scale"]))
    estimated_character_width = max(
        8,
        int(round(
            character_image.width
            * (estimated_character_height / max(character_image.height, 1))
        )),
    )
    _draw_semantic_prop(
        frame=frame,
        Image=Image,
        ImageDraw=ImageDraw,
        ImageFilter=ImageFilter,
        action=action,
        progress=progress,
        motion_plan=motion_plan,
        center_x=values["center_x"],
        ground_y=values["ground_y"],
        character_width=estimated_character_width,
        character_height=estimated_character_height,
    )
    if secondary_character_image is not None:
        if action == "interaction":
            rendered_secondary = secondary_character_image
        else:
            rendered_secondary = _select_motion_pose(
                secondary_character_motion_cells,
                motion_plan=motion_plan,
                progress=progress,
                Image=Image,
                role="secondary",
                cv2=cv2,
                np=np,
                interpolation_cache=interpolation_cache,
            ) or secondary_character_image
        if action in {"battle", "rescue", "interaction", "conversation"}:
            rendered_secondary = ImageOps.mirror(rendered_secondary)
        secondary_values = _secondary_motion_values(
            action=action,
            progress=progress,
            width=width,
            height=height,
        )
        _paste_character_layer(
            frame=frame,
            character_image=rendered_secondary,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
            center_x=secondary_values["center_x"],
            ground_y=secondary_values["ground_y"],
            scale=secondary_values["scale"],
            rotation=secondary_values["rotation"],
        )
    target_width, target_height = _paste_character_layer(
        frame=frame,
        character_image=rendered_character,
        Image=Image,
        ImageDraw=ImageDraw,
        ImageFilter=ImageFilter,
        center_x=values["center_x"],
        ground_y=values["ground_y"],
        scale=values["scale"],
        rotation=values["rotation"],
        ground_contact=values.get("ground_contact", 1.0),
    )
    _draw_action_effects(
        frame=frame,
        Image=Image,
        ImageDraw=ImageDraw,
        ImageFilter=ImageFilter,
        action=action,
        progress=progress,
        center_x=values["center_x"],
        ground_y=values["ground_y"],
        character_width=target_width,
        character_height=target_height,
        interaction_kind=motion_plan.get("interaction_kind"),
        effect_cells=action_fx_motion_cells,
        suppress_effects=suppress_action_effects,
    )
    fade = min(1.0, progress * 7.0, (1.0 - progress) * 7.0)
    frame = ImageEnhance.Brightness(frame).enhance(0.95 + 0.05 * fade)
    return ImageEnhance.Contrast(frame).enhance(1.018).convert("RGB")


def _write_video_frames(*, output_path: Path, frame_rate: int, frames, imageio, np) -> bytes:
    writer = imageio.get_writer(
        str(output_path),
        fps=frame_rate,
        codec="libx264",
        quality=9,
        macro_block_size=2,
        ffmpeg_log_level="error",
        output_params=[
            "-preset",
            LOCAL_VIDEO_ENCODER_PRESET,
            "-crf",
            str(LOCAL_VIDEO_ENCODER_CRF),
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()
    video_bytes = output_path.read_bytes()
    if not video_bytes:
        raise HfMediaError("Local video renderer returned an empty MP4 file.")
    return video_bytes


def _generate_local_video_bytes(
    *,
    image_bytes: bytes,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: int,
    motion_strength: int,
    motion_plan: Dict[str, Any],
) -> bytes:
    imageio, np, Image, _, ImageEnhance, _, ImageOps = _load_video_dependencies()
    width = _even_dimension(width)
    height = _even_dimension(height)
    frame_rate = min(max(int(frame_rate), 6), 30)
    total_frames = _normalize_frame_count(num_frames, frame_rate)

    try:
        source_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HfMediaError("Generated image bytes could not be opened for video rendering.") from exc

    with tempfile.TemporaryDirectory(prefix="fairytale_video_") as temp_dir:
        output_path = Path(temp_dir) / "scene.mp4"
        def render_frames():
            for index in range(total_frames):
                frame = _render_frame(
                    source_image=source_image,
                    Image=Image,
                    ImageEnhance=ImageEnhance,
                    ImageOps=ImageOps,
                    width=width,
                    height=height,
                    progress=index / max(total_frames - 1, 1),
                    motion_strength=motion_strength,
                    motion_plan=motion_plan,
                )
                yield ImageEnhance.Sharpness(frame).enhance(
                    LOCAL_VIDEO_FINAL_SHARPNESS
                )

        frames = render_frames()
        return _write_video_frames(
            output_path=output_path,
            frame_rate=frame_rate,
            frames=frames,
            imageio=imageio,
            np=np,
        )


def _generate_layered_video_bytes(
    *,
    background_bytes: bytes,
    character_bytes: bytes,
    secondary_character_bytes: Optional[bytes],
    character_motion_sheet_bytes: Optional[bytes],
    character_target_journey_sheet_bytes: Optional[bytes],
    character_run_cycle_sheet_bytes: Optional[bytes],
    character_jump_cycle_sheet_bytes: Optional[bytes],
    character_action_sheet_bytes: Optional[bytes],
    character_battle_cycle_sheet_bytes: Optional[bytes],
    character_magic_cycle_sheet_bytes: Optional[bytes],
    character_interaction_cycle_sheet_bytes: Optional[bytes],
    character_sit_cycle_sheet_bytes: Optional[bytes],
    character_stand_cycle_sheet_bytes: Optional[bytes],
    character_crawl_cycle_sheet_bytes: Optional[bytes],
    character_climb_cycle_sheet_bytes: Optional[bytes],
    action_fx_sheet_bytes: Optional[bytes],
    suppress_action_effects: bool,
    secondary_character_motion_sheet_bytes: Optional[bytes],
    width: int,
    height: int,
    num_frames: int,
    frame_rate: int,
    motion_strength: int,
    motion_plan: Dict[str, Any],
) -> bytes:
    imageio, np, Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps = _load_video_dependencies()
    try:
        import cv2
    except ImportError:
        cv2 = None
    width = _even_dimension(width)
    height = _even_dimension(height)
    frame_rate = min(max(int(frame_rate), 6), 30)
    total_frames = _normalize_frame_count(num_frames, frame_rate)
    try:
        background_image = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
        character_image = _prepare_character(
            Image.open(io.BytesIO(character_bytes)),
            Image,
        )
        secondary_character_image = (
            _prepare_character(
                Image.open(io.BytesIO(secondary_character_bytes)),
                Image,
            )
            if secondary_character_bytes
            else None
        )
        character_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_motion_sheet_bytes)),
                Image,
            )
            if character_motion_sheet_bytes
            else None
        )
        character_target_journey_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_target_journey_sheet_bytes)),
                Image,
            )
            if character_target_journey_sheet_bytes
            else None
        )
        character_run_cycle_motion_cells = (
            _prepare_run_cycle_sheet(
                Image.open(io.BytesIO(character_run_cycle_sheet_bytes)),
                Image,
            )
            if character_run_cycle_sheet_bytes
            else None
        )
        character_jump_cycle_motion_cells = (
            _prepare_run_cycle_sheet(
                Image.open(io.BytesIO(character_jump_cycle_sheet_bytes)),
                Image,
            )
            if character_jump_cycle_sheet_bytes
            else None
        )
        character_action_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_action_sheet_bytes)),
                Image,
            )
            if character_action_sheet_bytes
            else None
        )
        character_battle_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_battle_cycle_sheet_bytes)), Image
            )
            if character_battle_cycle_sheet_bytes else None
        )
        character_magic_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_magic_cycle_sheet_bytes)), Image
            )
            if character_magic_cycle_sheet_bytes else None
        )
        character_interaction_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_interaction_cycle_sheet_bytes)), Image
            )
            if character_interaction_cycle_sheet_bytes else None
        )
        character_sit_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_sit_cycle_sheet_bytes)), Image
            )
            if character_sit_cycle_sheet_bytes else None
        )
        character_stand_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_stand_cycle_sheet_bytes)), Image
            )
            if character_stand_cycle_sheet_bytes else None
        )
        character_crawl_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_crawl_cycle_sheet_bytes)), Image
            )
            if character_crawl_cycle_sheet_bytes else None
        )
        character_climb_cycle_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(character_climb_cycle_sheet_bytes)), Image
            )
            if character_climb_cycle_sheet_bytes else None
        )
        action_fx_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(action_fx_sheet_bytes)),
                Image,
                normalize=False,
            )
            if action_fx_sheet_bytes
            else None
        )
        secondary_character_motion_cells = (
            _prepare_motion_sheet(
                Image.open(io.BytesIO(secondary_character_motion_sheet_bytes)),
                Image,
            )
            if secondary_character_motion_sheet_bytes
            else None
        )
    except HfMediaError:
        raise
    except Exception as exc:
        raise HfMediaError("Character or background layer could not be opened for video rendering.") from exc

    with tempfile.TemporaryDirectory(prefix="fairytale_layered_video_") as temp_dir:
        output_path = Path(temp_dir) / "scene.mp4"
        interpolation_cache: Dict[Any, Any] = {}
        render_motion_plan = {
            **motion_plan,
            "_duration_seconds": total_frames / frame_rate,
        }
        render_scale = (
            LOCAL_VIDEO_RENDER_SCALE
            if (
                character_motion_cells is not None
                or character_target_journey_motion_cells is not None
                or character_run_cycle_motion_cells is not None
                or character_jump_cycle_motion_cells is not None
                or character_action_motion_cells is not None
                or character_battle_cycle_motion_cells is not None
                or character_magic_cycle_motion_cells is not None
                or character_interaction_cycle_motion_cells is not None
                or character_sit_cycle_motion_cells is not None
                or character_stand_cycle_motion_cells is not None
                or character_crawl_cycle_motion_cells is not None
                or character_climb_cycle_motion_cells is not None
                or secondary_character_motion_cells is not None
            )
            else 1
        )
        prepared_background = _prepare_background_stage(
            background_image,
            Image,
            ImageOps,
            width * render_scale,
            height * render_scale,
            render_motion_plan,
        )

        def render_frames():
            for index in range(total_frames):
                frame = _render_layered_frame(
                    background_image=background_image,
                    prepared_background=prepared_background,
                    character_image=character_image,
                    secondary_character_image=secondary_character_image,
                    character_motion_cells=character_motion_cells,
                    character_target_journey_motion_cells=(
                        character_target_journey_motion_cells
                    ),
                    character_run_cycle_motion_cells=(
                        character_run_cycle_motion_cells
                    ),
                    character_jump_cycle_motion_cells=(
                        character_jump_cycle_motion_cells
                    ),
                    character_action_motion_cells=character_action_motion_cells,
                    character_battle_cycle_motion_cells=character_battle_cycle_motion_cells,
                    character_magic_cycle_motion_cells=character_magic_cycle_motion_cells,
                    character_interaction_cycle_motion_cells=character_interaction_cycle_motion_cells,
                    character_sit_cycle_motion_cells=character_sit_cycle_motion_cells,
                    character_stand_cycle_motion_cells=character_stand_cycle_motion_cells,
                    character_crawl_cycle_motion_cells=character_crawl_cycle_motion_cells,
                    character_climb_cycle_motion_cells=character_climb_cycle_motion_cells,
                    action_fx_motion_cells=action_fx_motion_cells,
                    suppress_action_effects=suppress_action_effects,
                    secondary_character_motion_cells=secondary_character_motion_cells,
                    Image=Image,
                    ImageDraw=ImageDraw,
                    ImageEnhance=ImageEnhance,
                    ImageFilter=ImageFilter,
                    ImageOps=ImageOps,
                    width=width * render_scale,
                    height=height * render_scale,
                    progress=index / max(total_frames - 1, 1),
                    motion_strength=motion_strength,
                    motion_plan=render_motion_plan,
                    cv2=cv2,
                    np=np,
                    interpolation_cache=interpolation_cache,
                )
                if render_scale > 1:
                    frame = frame.resize(
                        (width, height),
                        getattr(Image, "Resampling", Image).LANCZOS,
                    )
                frame = ImageEnhance.Sharpness(frame).enhance(
                    LOCAL_VIDEO_FINAL_SHARPNESS
                )
                yield frame

        return _write_video_frames(
            output_path=output_path,
            frame_rate=frame_rate,
            frames=render_frames(),
            imageio=imageio,
            np=np,
        )


async def generate_hf_fairytale_video(
    *,
    image_bytes: bytes,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = LOCAL_VIDEO_DEFAULT_WIDTH,
    height: int = LOCAL_VIDEO_DEFAULT_HEIGHT,
    num_frames: int = 180,
    steps: int = 2,
    seed: Optional[int] = None,
    frame_rate: Optional[int] = None,
    motion_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not image_bytes:
        raise HfMediaError("image_bytes is empty.")

    context = dict(motion_context or {})
    scene_contract = context.get("scene_contract")
    if scene_contract:
        normalized_contract = normalize_scene_contract(
            scene_contract,
            character_key=context.get("character_key"),
            source=str(scene_contract.get("source") or "explicit"),
        )
        if not normalized_contract["valid"]:
            raise HfMediaError(
                "Video scene contract is invalid: "
                + ", ".join(normalized_contract["validation_errors"])
            )
        context = apply_scene_contract(context, normalized_contract)
        context["scene_contract"] = normalized_contract
    motion_plan = build_video_motion_plan(
        story_text=story_text,
        scene_action=context.get("scene_contract", {}).get("action")
        if isinstance(context.get("scene_contract"), dict)
        else None,
        scene_target=context.get("scene_contract", {}).get("target")
        if isinstance(context.get("scene_contract"), dict)
        else None,
        directionality=context.get("scene_contract", {}).get("background_direction")
        if isinstance(context.get("scene_contract"), dict)
        else None,
        character_pose=context.get("character_pose"),
        action_tags=context.get("action_tags"),
        effect_tags=context.get("effect_tags"),
        motion_modifier_tags=context.get("motion_modifier_tags"),
        required_props=(
            context.get("prop_tags")
            or (context.get("scene_contract") or {}).get("required_props")
        ),
        visual_anchor=(context.get("scene_contract") or {}).get("visual_anchor"),
        background_key=context.get("background_key"),
        action_semantics=context.get("action_semantics"),
        ensemble_profile=context.get("ensemble_profile"),
    )
    if scene_contract:
        motion_plan["scene_contract"] = context["scene_contract"]
    motion_plan["motion_focus"] = str(context.get("motion_focus") or "character")
    prompt = build_fairytale_video_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
        motion_plan=motion_plan,
    )
    normalized_frame_rate = frame_rate or LOCAL_VIDEO_FRAME_RATE
    normalized_frames = _normalize_frame_count(num_frames, normalized_frame_rate)
    background_bytes = context.get("background_bytes")
    character_bytes = context.get("character_bytes")
    secondary_character_bytes = context.get("secondary_character_bytes")
    character_motion_sheet_bytes = context.get("character_motion_sheet_bytes")
    character_target_journey_sheet_bytes = context.get(
        "character_target_journey_sheet_bytes"
    )
    character_run_cycle_sheet_bytes = context.get(
        "character_run_cycle_sheet_bytes"
    )
    character_jump_cycle_sheet_bytes = context.get(
        "character_jump_cycle_sheet_bytes"
    )
    character_action_sheet_bytes = context.get("character_action_sheet_bytes")
    character_battle_cycle_sheet_bytes = context.get("character_battle_cycle_sheet_bytes")
    character_magic_cycle_sheet_bytes = context.get("character_magic_cycle_sheet_bytes")
    character_interaction_cycle_sheet_bytes = context.get(
        "character_interaction_cycle_sheet_bytes"
    )
    character_sit_cycle_sheet_bytes = context.get("character_sit_cycle_sheet_bytes")
    character_stand_cycle_sheet_bytes = context.get("character_stand_cycle_sheet_bytes")
    character_crawl_cycle_sheet_bytes = context.get("character_crawl_cycle_sheet_bytes")
    character_climb_cycle_sheet_bytes = context.get("character_climb_cycle_sheet_bytes")
    action_fx_sheet_bytes = context.get("action_fx_sheet_bytes")
    requested_asset_version = str(
        context.get("motion_asset_version") or ""
    ).strip() or None
    suppress_action_effects = bool(context.get("suppress_action_effects"))
    secondary_character_motion_sheet_bytes = context.get(
        "secondary_character_motion_sheet_bytes"
    )
    has_secondary_character = isinstance(secondary_character_bytes, bytes)
    if motion_plan.get("requires_partner") and not has_secondary_character:
        raise HfMediaError(
            "Video scene contract requires a second character, but no partner asset was provided."
        )
    use_layered_animation = isinstance(background_bytes, bytes) and isinstance(character_bytes, bytes)
    use_motion_sheet = use_layered_animation and isinstance(
        character_motion_sheet_bytes,
        bytes,
    )
    use_target_journey_sheet = bool(
        use_layered_animation
        and isinstance(character_target_journey_sheet_bytes, bytes)
        and motion_plan.get("action") == "journey"
        and motion_plan.get("pace") in {"walk", "run"}
        and motion_plan.get("target") != "scene"
    )
    use_run_cycle_sheet = bool(
        use_layered_animation
        and isinstance(character_run_cycle_sheet_bytes, bytes)
        and motion_plan.get("action") == "journey"
        and motion_plan.get("pace") in {"walk", "run"}
    )
    use_crawl_cycle_sheet = bool(
        use_layered_animation
        and isinstance(character_crawl_cycle_sheet_bytes, bytes)
        and motion_plan.get("action") == "journey"
        and motion_plan.get("pace") == "crawl"
    )
    use_climb_cycle_sheet = bool(
        use_layered_animation
        and isinstance(character_climb_cycle_sheet_bytes, bytes)
        and motion_plan.get("action") == "journey"
        and motion_plan.get("pace") == "climb"
    )
    use_jump_cycle_sheet = bool(
        use_layered_animation
        and isinstance(character_jump_cycle_sheet_bytes, bytes)
        and motion_plan.get("action") == "jump"
    )
    use_action_sheet = bool(
        use_layered_animation
        and isinstance(character_action_sheet_bytes, bytes)
        and motion_plan.get("action") in ACTION_SHEET_ACTIONS
    )
    dedicated_cycle_bytes = (
        character_battle_cycle_sheet_bytes
        if motion_plan.get("action") == "battle"
        else character_magic_cycle_sheet_bytes
        if motion_plan.get("action") == "magic"
        else character_interaction_cycle_sheet_bytes
        if motion_plan.get("action") in {"rescue", "interaction"}
        else character_sit_cycle_sheet_bytes
        if motion_plan.get("action") == "sit"
        else character_stand_cycle_sheet_bytes
        if motion_plan.get("action") == "stand"
        else character_crawl_cycle_sheet_bytes
        if motion_plan.get("action") == "journey" and motion_plan.get("pace") == "crawl"
        else character_climb_cycle_sheet_bytes
        if motion_plan.get("action") == "journey" and motion_plan.get("pace") == "climb"
        else None
    )
    use_dedicated_action_cycle = bool(
        use_layered_animation and isinstance(dedicated_cycle_bytes, bytes)
    )
    use_action_fx_sheet = bool(
        use_layered_animation
        and isinstance(action_fx_sheet_bytes, bytes)
        and not suppress_action_effects
    )
    action_name = str(motion_plan.get("action") or "idle")
    has_semantic_action_asset = bool(
        (action_name == "jump" and use_jump_cycle_sheet)
        or (action_name in ACTION_SHEET_ACTIONS and use_action_sheet)
        or (
            action_name in {"battle", "magic", "rescue", "interaction", "sit", "stand"}
            and use_dedicated_action_cycle
        )
        or (action_name == "journey" and use_crawl_cycle_sheet)
        or (action_name == "journey" and use_climb_cycle_sheet)
    )
    uses_reference_fallback = bool(
        use_layered_animation
        and action_name in REFERENCE_FALLBACK_ACTIONS
        and not has_semantic_action_asset
    )
    motion_sheet_animation_mode = {
        "jump": "motion_sheet_jump_v5",
        "wave": "motion_sheet_wave_v5",
        "magic": "motion_sheet_magic_v5",
        "investigate": "motion_sheet_investigate_v6",
        "battle": "motion_sheet_battle_v6",
        "rescue": "motion_sheet_rescue_v6",
        "interaction": (
            "motion_sheet_handoff_v6"
            if motion_plan.get("interaction_kind") == "handoff_receive"
            else "motion_sheet_action_v4"
        ),
    }.get(str(motion_plan.get("action") or ""), "motion_sheet_action_v4")

    if use_layered_animation:
        video_bytes = await asyncio.to_thread(
            _generate_layered_video_bytes,
            background_bytes=background_bytes,
            character_bytes=character_bytes,
            secondary_character_bytes=(
                secondary_character_bytes
                if isinstance(secondary_character_bytes, bytes)
                else None
            ),
            character_motion_sheet_bytes=(
                character_motion_sheet_bytes if use_motion_sheet else None
            ),
            character_target_journey_sheet_bytes=(
                character_target_journey_sheet_bytes
                if isinstance(character_target_journey_sheet_bytes, bytes)
                else None
            ),
            character_run_cycle_sheet_bytes=(
                character_run_cycle_sheet_bytes
                if use_run_cycle_sheet
                else None
            ),
            character_jump_cycle_sheet_bytes=(
                character_jump_cycle_sheet_bytes
                if use_jump_cycle_sheet
                else None
            ),
            character_action_sheet_bytes=(
                character_action_sheet_bytes if use_action_sheet else None
            ),
            character_battle_cycle_sheet_bytes=(
                character_battle_cycle_sheet_bytes
                if use_dedicated_action_cycle and motion_plan.get("action") == "battle"
                else None
            ),
            character_magic_cycle_sheet_bytes=(
                character_magic_cycle_sheet_bytes
                if use_dedicated_action_cycle and motion_plan.get("action") == "magic"
                else None
            ),
            character_interaction_cycle_sheet_bytes=(
                character_interaction_cycle_sheet_bytes
                if use_dedicated_action_cycle
                and motion_plan.get("action") in {"rescue", "interaction"}
                else None
            ),
            character_sit_cycle_sheet_bytes=(
                character_sit_cycle_sheet_bytes
                if isinstance(character_sit_cycle_sheet_bytes, bytes)
                and motion_plan.get("action") in {"sit", "stand"}
                else None
            ),
            character_stand_cycle_sheet_bytes=(
                character_stand_cycle_sheet_bytes
                if isinstance(character_stand_cycle_sheet_bytes, bytes)
                and motion_plan.get("action") in {"sit", "stand"}
                else None
            ),
            character_crawl_cycle_sheet_bytes=(
                character_crawl_cycle_sheet_bytes
                if use_crawl_cycle_sheet
                else None
            ),
            character_climb_cycle_sheet_bytes=(
                character_climb_cycle_sheet_bytes
                if use_climb_cycle_sheet
                else None
            ),
            action_fx_sheet_bytes=(
                action_fx_sheet_bytes if use_action_fx_sheet else None
            ),
            suppress_action_effects=suppress_action_effects,
            secondary_character_motion_sheet_bytes=(
                secondary_character_motion_sheet_bytes
                if isinstance(secondary_character_motion_sheet_bytes, bytes)
                else None
            ),
            width=width,
            height=height,
            num_frames=normalized_frames,
            frame_rate=normalized_frame_rate,
            motion_strength=steps,
            motion_plan=motion_plan,
        )
        if use_jump_cycle_sheet:
            animation_mode = (
                f"identity_locked_jump_cycle_{requested_asset_version or 'v23'}_smoothed"
            )
        elif use_crawl_cycle_sheet or use_climb_cycle_sheet:
            animation_mode = (
                "identity_locked_crawl_cycle_v2"
                if use_crawl_cycle_sheet
                else "identity_locked_climb_cycle_v2"
            )
        elif use_dedicated_action_cycle:
            animation_mode = (
                "identity_locked_action_cycle_"
                f"{requested_asset_version or 'v23'}_stable_alpha"
            )
        elif use_action_sheet:
            animation_mode = (
                "identity_locked_action_sheet_"
                f"{requested_asset_version or 'v23'}_grounded_smooth"
            )
        elif use_run_cycle_sheet:
            animation_mode = (
                "sprite_run_cycle_road_v16_stride_amplified"
                if motion_plan.get("pace") == "run"
                else "sprite_walk_cycle_road_v16_slow_stride"
            )
        elif use_target_journey_sheet:
            animation_mode = "target_journey_action_v4"
        elif uses_reference_fallback:
            animation_mode = "reference_transform_v29_semantic_fallback"
        elif use_motion_sheet:
            animation_mode = motion_sheet_animation_mode
        else:
            animation_mode = "layered_action"
    else:
        video_bytes = await asyncio.to_thread(
            _generate_local_video_bytes,
            image_bytes=image_bytes,
            width=width,
            height=height,
            num_frames=normalized_frames,
            frame_rate=normalized_frame_rate,
            motion_strength=steps,
            motion_plan=motion_plan,
        )
        animation_mode = "camera_fallback"

    if use_jump_cycle_sheet:
        motion_asset_tier = "dedicated_jump_cycle"
    elif use_crawl_cycle_sheet or use_climb_cycle_sheet:
        motion_asset_tier = "dedicated_travel_cycle"
    elif use_dedicated_action_cycle:
        motion_asset_tier = "dedicated_action_cycle"
    elif use_action_sheet:
        motion_asset_tier = "identity_action_sheet"
    elif use_run_cycle_sheet:
        motion_asset_tier = "identity_run_cycle"
    elif use_target_journey_sheet:
        motion_asset_tier = "target_journey_sheet"
    elif uses_reference_fallback:
        motion_asset_tier = "reference_transform"
    elif use_motion_sheet:
        motion_asset_tier = "generic_motion_sheet"
    elif use_layered_animation:
        motion_asset_tier = "reference_transform"
    else:
        motion_asset_tier = "camera_only"

    action_sheet_used = bool(
        use_action_sheet and not use_dedicated_action_cycle
    )
    versioned_action = (
        use_jump_cycle_sheet
        or action_sheet_used
        or (
            use_dedicated_action_cycle
            and motion_plan.get("action") in {"battle", "interaction", "rescue"}
        )
        or use_crawl_cycle_sheet
        or use_climb_cycle_sheet
    )
    selected_asset_version = (
        requested_asset_version or "v23"
        if versioned_action
        else None
    )
    legacy_motion_asset_fallback = bool(
        versioned_action
        and requested_asset_version
        and requested_asset_version not in {"v2", "v28"}
    )
    motion_fallback_used = bool(
        uses_reference_fallback
        or legacy_motion_asset_fallback
        or (
            use_layered_animation
            and action_name in {
                "jump", "wave", "magic", "battle", "rescue",
                "investigate", "interaction", "journey",
            }
            and not has_semantic_action_asset
        )
    )
    return {
        "video_bytes": video_bytes,
        "content_type": "video/mp4",
        "provider": LOCAL_VIDEO_PROVIDER,
        "model": LOCAL_VIDEO_MODEL,
        "prompt": prompt,
        "parameters": {
            "width": _even_dimension(width),
            "height": _even_dimension(height),
            "num_frames": normalized_frames,
            "frame_rate": min(max(int(normalized_frame_rate), 6), 30),
            "duration_seconds": round(
                normalized_frames / min(max(int(normalized_frame_rate), 6), 30),
                3,
            ),
            "motion_strength": int(steps),
            "motion_focus": motion_plan.get("motion_focus", "character"),
            "effect_style": "action-anchored-subtle-v6",
            "encoder": {
                "codec": "libx264",
                "crf": LOCAL_VIDEO_ENCODER_CRF,
                "preset": LOCAL_VIDEO_ENCODER_PRESET,
                "final_sharpness": LOCAL_VIDEO_FINAL_SHARPNESS,
            },
            "animation_mode": animation_mode,
            "compositor_mode": (
                "cinematic_action_compositor_v29_stable_alpha"
                if use_layered_animation
                else "camera_fallback"
            ),
            "motion_asset_tier": motion_asset_tier,
            "motion_asset_version": selected_asset_version,
            "action_sheet_version": (
                selected_asset_version if action_sheet_used else None
            ),
            "dedicated_action_cycle_version": (
                selected_asset_version
                if use_dedicated_action_cycle
                and motion_plan.get("action") in {"battle", "interaction", "rescue", "sit", "stand", "journey"}
                else None
            ),
            "motion_fallback_used": motion_fallback_used,
            "motion_fallback_reason": (
                "legacy_action_asset_version"
                if legacy_motion_asset_fallback
                else "semantic_action_asset_missing"
                if motion_fallback_used
                else None
            ),
            "action_effects_suppressed": suppress_action_effects,
            "render_scale": (
                LOCAL_VIDEO_RENDER_SCALE
                if use_motion_sheet or use_target_journey_sheet
                or use_run_cycle_sheet or use_jump_cycle_sheet
                or use_action_sheet or use_dedicated_action_cycle
                or use_crawl_cycle_sheet or use_climb_cycle_sheet
                or isinstance(secondary_character_motion_sheet_bytes, bytes)
                else 1
            ),
            "motion_plan": motion_plan,
            "co_star_included": bool(
                use_layered_animation and has_secondary_character
            ),
            "motion_sheet_character_key": (
                context.get("character_key")
                if motion_asset_tier == "generic_motion_sheet"
                else None
            ),
            "target_facing_character": (
                use_target_journey_sheet or use_run_cycle_sheet
            ),
            "identity_locked_run_cycle": use_run_cycle_sheet,
            "run_cycle_character_key": (
                context.get("character_key") if use_run_cycle_sheet else None
            ),
            "jump_cycle_character_key": (
                context.get("character_key") if use_jump_cycle_sheet else None
            ),
            "action_sheet_character_key": (
                context.get("character_key")
                if motion_asset_tier == "identity_action_sheet"
                else None
            ),
            "dedicated_action_cycle_character_key": (
                context.get("character_key") if use_dedicated_action_cycle else None
            ),
            "target_journey_sheet_character_key": (
                context.get("character_key") if use_target_journey_sheet else None
            ),
            "background_motion": (
                "wide-target-tracking-pan"
                if use_target_journey_sheet or use_run_cycle_sheet
                else "standard-camera"
            ),
            "background_stage": (
                _background_stage_spec(
                    _even_dimension(width),
                    _even_dimension(height),
                    motion_plan,
                )
                if use_layered_animation
                else None
            ),
            "journey_route": (
                {
                    "background_key": motion_plan.get("background_key"),
                    "coordinate_space": "normalized-background-stage",
                    "points": [
                        list(point)
                        for point in BACKGROUND_JOURNEY_ROUTES.get(
                            str(motion_plan.get("background_key") or ""),
                            (),
                        )
                    ],
                }
                if use_target_journey_sheet or use_run_cycle_sheet
                else None
            ),
            "secondary_motion_sheet_character_key": (
                context.get("secondary_character_key")
                if isinstance(secondary_character_motion_sheet_bytes, bytes)
                else None
            ),
            "seed": seed,
        },
    }
