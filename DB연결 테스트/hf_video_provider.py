import asyncio
import io
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cinematic_animatic import (
    ANIMATION_MODE as CINEMATIC_ANIMATION_MODE,
    apply_cinematic_camera,
    apply_cinematic_cut_effect,
    apply_cinematic_foreground,
    resolve_cinematic_shot,
    supports_cinematic_animatic,
)
from hf_media_common import HfMediaError
from media_compositor import build_character_shadow, prepare_story_scene_layers
from story_stage_renderer import (
    STAGE_ID,
    compose_story_stage_background,
    composite_story_action_effects,
    prepare_story_stage,
    supports_story_stage,
)

LOCAL_VIDEO_PROVIDER = (os.getenv("VIDEO_PROVIDER") or "local-animation").strip()
LOCAL_VIDEO_MODEL = (
    os.getenv("LOCAL_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "storybook-cinematic-animatic-v2"
).strip()
LOCAL_VIDEO_FRAME_RATE = int(os.getenv("LOCAL_VIDEO_FRAME_RATE", "24"))
LOCAL_VIDEO_DURATION_SECONDS = float(os.getenv("LOCAL_VIDEO_DURATION_SECONDS", "4.0"))
LOCAL_VIDEO_MAX_DURATION_SECONDS = min(
    15.0,
    max(1.0, float(os.getenv("LOCAL_VIDEO_MAX_DURATION_SECONDS", "15.0"))),
)
LOCAL_VIDEO_TIMEOUT_SECONDS = min(
    15.0,
    max(5.0, float(os.getenv("LOCAL_VIDEO_TIMEOUT_SECONDS", "15.0"))),
)
ACTION_RENDER_FRAME_TARGET = 24
ACTION_SEGMENT_TRANSITION_SECONDS = 0.25
ACTION_SEGMENT_TRANSITION_SAMPLES = 8
CINEMATIC_POSE_TRANSITION_FRAMES = 2


def get_hf_video_config() -> Dict[str, Any]:
    return {
        "configured": True,
        "video_supported": True,
        "video_provider": LOCAL_VIDEO_PROVIDER,
        "video_model": LOCAL_VIDEO_MODEL,
        "video_task": "profile-driven-cinematic-animatic",
        "video_requires_gpu": False,
        "video_requires_external_api": False,
        "video_default_frame_rate": LOCAL_VIDEO_FRAME_RATE,
        "video_default_duration_seconds": LOCAL_VIDEO_DURATION_SECONDS,
        "video_max_duration_seconds": LOCAL_VIDEO_MAX_DURATION_SECONDS,
        "video_timeout_seconds": LOCAL_VIDEO_TIMEOUT_SECONDS,
    }


def build_fairytale_video_prompt(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
) -> str:
    scene = " ".join(story_text.split())[:500]
    genre_text = f"{genre} fairytale" if genre else "fairytale"
    age_text = f"for {age} year old children" if age else "for children"
    return (
        "storybook still image animation, gentle camera movement, "
        "warm magical mood, no generated text, "
        f"{genre_text}, {age_text}, scene: {scene}"
    )


def _load_video_dependencies():
    try:
        import cv2
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise HfMediaError(
            "Local video generation needs pillow, numpy, OpenCV, imageio, "
            "and imageio-ffmpeg. "
            "Run `pip install -r requirements.txt` in the backend folder."
        ) from exc
    return (
        imageio,
        np,
        Image,
        ImageEnhance,
        ImageOps,
        cv2,
        ImageDraw,
        ImageFilter,
    )


def _even_dimension(value: int, minimum: int = 256) -> int:
    normalized = max(minimum, int(value))
    return normalized if normalized % 2 == 0 else normalized - 1


def _normalize_frame_count(num_frames: int, frame_rate: int) -> int:
    requested = max(1, int(num_frames))
    default_frames = max(1, int(round(LOCAL_VIDEO_DURATION_SECONDS * frame_rate)))
    max_frames = max(1, int(LOCAL_VIDEO_MAX_DURATION_SECONDS * frame_rate))
    return min(max(requested, default_frames), max_frames)


def _quality_render_scale(steps: int) -> float:
    return min(1.5, max(1.0, 1.0 + int(steps) * 0.025))


def _ease_in_out(progress: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * progress)


def _contains_action_keyword(text: str, keyword: str) -> bool:
    if keyword.isascii():
        return bool(re.search(rf"\b{re.escape(keyword)}\b", text))
    return keyword in text


def select_motion_preset(story_text: str) -> str:
    normalized = " ".join(story_text.lower().split())
    action_groups = (
        (
            "fight",
            (
                "fight",
                "battle",
                "combat",
                "attack",
                "slash",
                "defend",
                "block",
                "sword",
                "\uc2f8\uc6b0",
                "\uc804\ud22c",
                "\uacf5\uaca9",
                "\uacb0\ud22c",
                "\uac80\uc744",
                "\uce7c\uc744",
                "\ubca0\uc5b4",
                "\ub9c9\uc544",
            ),
        ),
        (
            "run",
            (
                "run",
                "runs",
                "running",
                "race",
                "sprint",
                "dash",
                "\ub2ec\ub9ac",
                "\ub6f0",
            ),
        ),
        (
            "magic",
            (
                "magic",
                "spell",
                "cast",
                "casts",
                "\ub9c8\ubc95",
                "\uc8fc\ubb38",
            ),
        ),
        (
            "jump",
            ("jump", "jumps", "leap", "hop", "\uc810\ud504", "\ub6f0\uc5b4"),
        ),
        (
            "fly",
            ("fly", "flies", "flying", "float", "soar", "\ub0a0\uc544", "\ube44\ud589"),
        ),
        (
            "walk",
            (
                "walk",
                "walks",
                "walking",
                "stroll",
                "\uac77",
                "\uac78\uc5b4",
                "\uc0b0\ucc45",
            ),
        ),
        ("wave", ("wave", "waving", "greet", "\uc778\uc0ac", "\uc190\uc744 \ud754\ub4e4")),
        (
            "talk",
            ("talk", "speak", "whisper", "sing", "\ub9d0\ud558", "\uc774\uc57c\uae30", "\ub178\ub798"),
        ),
    )
    for preset, keywords in action_groups:
        if any(_contains_action_keyword(normalized, keyword) for keyword in keywords):
            return preset
    keyword_groups = (
        ("run", ("run", "running", "race", "sprint", "달리", "뛰어가", "도망")),
        ("jump", ("jump", "leap", "hop", "점프", "뛰어오", "껑충")),
        ("fly", ("fly", "flies", "flying", "float", "soar", "날아", "비행", "떠오")),
        ("walk", ("walk", "walking", "stroll", "걷", "산책", "다가가")),
        ("wave", ("wave", "waving", "greet", "인사", "손을 흔", "손 흔")),
        ("talk", ("talk", "speak", "whisper", "sing", "말하", "이야기", "노래")),
    )
    for preset, keywords in keyword_groups:
        if any(_contains_action_keyword(normalized, keyword) for keyword in keywords):
            return preset
    return "idle"


def _character_motion(
    *,
    preset: str,
    progress: float,
    width: int,
    height: int,
    motion_strength: int,
    elapsed_seconds: Optional[float] = None,
) -> Dict[str, float]:
    strength = 0.7 + 0.3 * (min(max(int(motion_strength), 1), 8) / 8.0)
    elapsed = progress * LOCAL_VIDEO_DURATION_SECONDS if elapsed_seconds is None else elapsed_seconds
    cadence = {
        "idle": 0.45,
        "walk": 1.5,
        "run": 2.4,
        "fight": 1.1,
        "magic": 0.8,
        "jump": 0.75,
        "fly": 0.55,
        "wave": 1.2,
        "talk": 1.1,
    }.get(preset, 0.45)
    phase = math.tau * elapsed * cadence
    sway = math.sin(phase)
    pulse = math.sin(phase * 2.0)
    values = {
        "x": sway * width * 0.006 * strength,
        "y": -abs(pulse) * height * 0.007 * strength,
        "angle": sway * 1.1 * strength,
        "scale_x": 1.0 + pulse * 0.004 * strength,
        "scale_y": 1.0 + pulse * 0.012 * strength,
        "shadow_scale": 1.0 - abs(pulse) * 0.035 * strength,
        "shadow_opacity": 92.0 - abs(pulse) * 8.0 * strength,
    }
    if preset == "walk":
        values.update(
            x=sway * width * 0.007 * strength,
            y=-abs(pulse) * height * 0.009 * strength,
            angle=sway * 0.85 * strength,
        )
    elif preset == "run":
        values.update(
            x=sway * width * 0.008 * strength,
            y=-abs(pulse) * height * 0.012 * strength,
            angle=sway * 1.0 * strength,
            scale_x=1.0 + pulse * 0.005 * strength,
        )
    elif preset == "fight":
        values.update(
            x=sway * width * 0.006 * strength,
            y=-abs(pulse) * height * 0.006 * strength,
            angle=sway * 0.7 * strength,
            scale_x=1.0 + pulse * 0.003 * strength,
            scale_y=1.0 + pulse * 0.006 * strength,
        )
    elif preset == "magic":
        values.update(
            x=0.0,
            y=-abs(pulse) * height * 0.008 * strength,
            angle=sway * 0.45 * strength,
            scale_x=1.0 + pulse * 0.004 * strength,
            scale_y=1.0 + pulse * 0.008 * strength,
        )
    elif preset == "jump":
        lift = max(0.0, math.sin(phase)) * height * 0.14 * strength
        values.update(
            x=sway * width * 0.014 * strength,
            y=-lift,
            angle=sway * 2.0 * strength,
            scale_y=1.0 + max(0.0, math.sin(phase)) * 0.025 * strength,
            shadow_scale=max(0.5, 1.0 - lift / max(height * 0.25, 1)),
            shadow_opacity=max(35.0, 92.0 - lift * 0.45),
        )
    elif preset == "fly":
        lift = (0.55 + 0.25 * math.sin(phase)) * height * 0.11 * strength
        values.update(
            x=sway * width * 0.025 * strength,
            y=-lift,
            angle=sway * 2.6 * strength,
            shadow_scale=0.55,
            shadow_opacity=42.0,
        )
    elif preset == "wave":
        values.update(
            x=sway * width * 0.009 * strength,
            y=-abs(pulse) * height * 0.006 * strength,
            angle=sway * 2.4 * strength,
            scale_x=1.0 + pulse * 0.009 * strength,
        )
    elif preset == "talk":
        values.update(
            y=-abs(pulse) * height * 0.005 * strength,
            angle=sway * 1.2 * strength,
            scale_y=1.0 + pulse * 0.014 * strength,
        )
    return values


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
):
    eased = _ease_in_out(progress)
    zoom_start = 1.04
    zoom_end = 1.08 + min(max(motion_strength, 1), 8) * 0.01
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
    x_offset = int(max_x * eased)
    y_offset = int(max_y * (1.0 - eased) * 0.5)
    frame = fitted.crop((x_offset, y_offset, x_offset + width, y_offset + height))

    fade = min(1.0, progress * 6.0, (1.0 - progress) * 6.0)
    brightness = 0.94 + 0.06 * fade
    contrast = 1.02
    frame = ImageEnhance.Brightness(frame).enhance(brightness)
    frame = ImageEnhance.Contrast(frame).enhance(contrast)
    return frame


def _split_action_cycle_frames(
    action_cycle_bytes: bytes,
    Image,
    *,
    layout: Optional[str] = "2x2",
    frame_count: Optional[int] = None,
) -> List[Any]:
    if not action_cycle_bytes:
        return []
    normalized_layout = (layout or "2x2").strip().lower()
    try:
        columns_text, rows_text = normalized_layout.split("x", 1)
        columns = int(columns_text)
        rows = int(rows_text)
    except (TypeError, ValueError):
        return []
    if columns < 1 or rows < 1 or columns * rows > 16:
        return []

    with Image.open(io.BytesIO(action_cycle_bytes)) as source:
        sheet = source.convert("RGBA")
    cell_width = sheet.width // columns
    cell_height = sheet.height // rows
    requested_count = frame_count or columns * rows
    requested_count = min(max(int(requested_count), 1), columns * rows)
    frames = []
    for index in range(requested_count):
        column = index % columns
        row = index // columns
        frame = sheet.crop(
            (
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                (row + 1) * cell_height,
            )
        )
        alpha_bounds = frame.getchannel("A").getbbox()
        if alpha_bounds is not None:
            frames.append(frame.crop(alpha_bounds))
    return frames


def _prepare_action_cycle_frames(
    action_cycle_bytes: bytes,
    Image,
    *,
    width: int,
    height: int,
    layout: Optional[str] = "2x2",
    frame_count: Optional[int] = None,
) -> Tuple[List[Any], Optional[Tuple[int, int]]]:
    frames = _split_action_cycle_frames(
        action_cycle_bytes,
        Image,
        layout=layout,
        frame_count=frame_count,
    )
    if len(frames) < 2:
        return [], None

    def foot_anchor(frame) -> float:
        alpha = frame.getchannel("A")
        lower_start = round(frame.height * 0.58)
        lower_bounds = alpha.crop(
            (0, lower_start, frame.width, frame.height)
        ).getbbox()
        if lower_bounds is None:
            return frame.width / 2.0
        return (lower_bounds[0] + lower_bounds[2]) / 2.0

    target_height = round(height * 0.70)
    max_width = round(width * 0.82)
    raw_foot_anchors = [foot_anchor(frame) for frame in frames]
    anchored_width = max(raw_foot_anchors) + max(
        frame.width - anchor
        for frame, anchor in zip(frames, raw_foot_anchors)
    )
    common_scale = min(
        target_height / max(frame.height for frame in frames),
        max_width / max(frame.width for frame in frames),
        max_width / max(anchored_width, 1.0),
    )
    resized_frames = []
    for frame in frames:
        resized_frames.append(
            frame.resize(
                (
                    max(1, round(frame.width * common_scale)),
                    max(1, round(frame.height * common_scale)),
                ),
                getattr(Image, "Resampling", Image).LANCZOS,
            )
        )

    foot_anchors = [foot_anchor(frame) for frame in resized_frames]
    left_extent = math.ceil(max(foot_anchors))
    right_extent = math.ceil(
        max(
            frame.width - anchor
            for frame, anchor in zip(resized_frames, foot_anchors)
        )
    )
    canvas_width = left_extent + right_extent
    canvas_height = max(frame.height for frame in resized_frames)
    normalized_frames = []
    for frame, foot_anchor in zip(resized_frames, foot_anchors):
        canvas = Image.new(
            "RGBA",
            (canvas_width, canvas_height),
            (0, 0, 0, 0),
        )
        canvas.alpha_composite(
            frame,
            (
                round(left_extent - foot_anchor),
                canvas_height - frame.height,
            ),
        )
        normalized_frames.append(canvas)

    position = (
        (width - canvas_width) // 2,
        max(0, height - canvas_height - round(height * 0.035)),
    )
    return normalized_frames, position


def _action_cycle_frame_index(
    action_name: Optional[str],
    elapsed_seconds: float,
    frame_count: int,
    cycle_seconds: Optional[float] = None,
    cycle_progress: Optional[float] = None,
) -> int:
    frame_index, _, _ = _action_cycle_frame_sample(
        action_name,
        elapsed_seconds,
        frame_count,
        cycle_seconds=cycle_seconds,
        cycle_progress=cycle_progress,
    )
    return frame_index


def _action_cycle_frame_sample(
    action_name: Optional[str],
    elapsed_seconds: float,
    frame_count: int,
    cycle_seconds: Optional[float] = None,
    cycle_progress: Optional[float] = None,
    frame_rate: int = LOCAL_VIDEO_FRAME_RATE,
) -> Tuple[int, int, float]:
    if frame_count <= 1:
        return 0, 0, 0.0
    elapsed = max(0.0, elapsed_seconds)
    default_seconds = {
        "walk": 1.0,
        "run": 0.8,
        "fight": 3.0,
        "jump": 2.4,
        "magic": 3.0,
    }.get(action_name or "", 1.0)
    duration = max(0.25, float(cycle_seconds or default_seconds))
    if cycle_progress is not None and action_name not in {"walk", "run"}:
        phase = min(0.999999, max(0.0, cycle_progress))
    else:
        phase = (elapsed % duration) / duration
    weight_presets = {
        "walk": (2, 2, 2, 2, 2, 2),
        "run": (2, 1, 1, 2, 1, 1),
        "fight": (3, 5, 7, 4, 5, 6),
        "jump": (2, 4, 5, 9, 2, 2),
        "magic": (2, 6, 6, 5, 5, 7),
    }
    weights = weight_presets.get(action_name or "")
    if not weights or len(weights) != frame_count:
        weights = tuple(1 for _ in range(frame_count))
    total_weight = sum(weights)
    weighted_position = phase * total_weight
    cumulative = 0.0
    for index, weight in enumerate(weights):
        frame_start = cumulative
        cumulative += weight
        if weighted_position >= cumulative:
            continue

        local_progress = (weighted_position - frame_start) / max(weight, 1e-9)
        should_loop = cycle_progress is None
        next_index = (
            (index + 1) % frame_count
            if index < frame_count - 1 or should_loop
            else index
        )
        if next_index == index:
            return index, index, 0.0
        return index, next_index, local_progress
    return frame_count - 1, frame_count - 1, 0.0


def _build_optical_transition_pair(
    first,
    second,
    sample_count: int,
    Image,
    np,
    cv2,
    *,
    include_endpoint: bool,
):
    first_array = np.asarray(first, dtype=np.uint8)
    second_array = np.asarray(second, dtype=np.uint8)

    def flow_gray(frame):
        alpha = frame[:, :, 3:4].astype(np.float32) / 255.0
        composite = (
            frame[:, :, :3].astype(np.float32) * alpha
            + 127.0 * (1.0 - alpha)
        )
        return cv2.cvtColor(
            composite.astype(np.uint8),
            cv2.COLOR_RGB2GRAY,
        )

    optical_flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    forward = optical_flow.calc(
        flow_gray(first_array),
        flow_gray(second_array),
        None,
    )
    backward = optical_flow.calc(
        flow_gray(second_array),
        flow_gray(first_array),
        None,
    )
    frame_height, frame_width = first_array.shape[:2]
    grid_x, grid_y = np.meshgrid(
        np.arange(frame_width, dtype=np.float32),
        np.arange(frame_height, dtype=np.float32),
    )

    pair_frames = []
    divisor = max(1, sample_count - 1 if include_endpoint else sample_count)
    for sample_index in range(sample_count):
        amount = sample_index / divisor
        if sample_index == 0:
            pair_frames.append(first)
            continue
        if include_endpoint and sample_index == sample_count - 1:
            pair_frames.append(second)
            continue
        if amount < 0.5:
            source = first_array
            flow = forward
            warp_amount = amount
        else:
            source = second_array
            flow = backward
            warp_amount = 1.0 - amount
        warped = cv2.remap(
            source,
            grid_x - flow[:, :, 0] * warp_amount,
            grid_y - flow[:, :, 1] * warp_amount,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        pair_frames.append(Image.fromarray(warped, "RGBA"))
    return pair_frames


def _build_action_transition_frames(frames, Image, np, cv2):
    if len(frames) < 2:
        return [], 1

    samples_per_key = max(
        2,
        math.ceil(ACTION_RENDER_FRAME_TARGET / len(frames)),
    )
    transitions = [
        _build_optical_transition_pair(
            frame,
            frames[(index + 1) % len(frames)],
            samples_per_key,
            Image,
            np,
            cv2,
            include_endpoint=False,
        )
        for index, frame in enumerate(frames)
    ]
    return transitions, samples_per_key


def _pad_action_frame_pair(
    first,
    first_position: Tuple[int, int],
    second,
    second_position: Tuple[int, int],
    Image,
):
    left = min(first_position[0], second_position[0])
    top = min(first_position[1], second_position[1])
    right = max(
        first_position[0] + first.width,
        second_position[0] + second.width,
    )
    bottom = max(
        first_position[1] + first.height,
        second_position[1] + second.height,
    )
    size = (right - left, bottom - top)
    first_canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    second_canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    first_canvas.alpha_composite(
        first,
        (first_position[0] - left, first_position[1] - top),
    )
    second_canvas.alpha_composite(
        second,
        (second_position[0] - left, second_position[1] - top),
    )
    return first_canvas, second_canvas, (left, top)


def _pad_action_frame_sequence(frame_positions, Image):
    left = min(position[0] for _, position in frame_positions)
    top = min(position[1] for _, position in frame_positions)
    right = max(
        position[0] + frame.width
        for frame, position in frame_positions
    )
    bottom = max(
        position[1] + frame.height
        for frame, position in frame_positions
    )
    size = (right - left, bottom - top)
    canvases = []
    for frame, position in frame_positions:
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(
            frame,
            (position[0] - left, position[1] - top),
        )
        canvases.append(canvas)
    return canvases, (left, top)


def _smootherstep(value: float) -> float:
    normalized = min(1.0, max(0.0, value))
    return normalized * normalized * normalized * (
        normalized * (normalized * 6.0 - 15.0) + 10.0
    )


def _interpolate_action_keyframes(
    frame: float,
    keyframes: List[Tuple[float, float]],
) -> float:
    if frame <= keyframes[0][0]:
        return keyframes[0][1]
    if frame >= keyframes[-1][0]:
        return keyframes[-1][1]
    for (start_frame, start_value), (end_frame, end_value) in zip(
        keyframes,
        keyframes[1:],
    ):
        if start_frame <= frame <= end_frame:
            span = max(1e-9, end_frame - start_frame)
            progress = _smootherstep((frame - start_frame) / span)
            return start_value + (end_value - start_value) * progress
    return keyframes[-1][1]


def _action_cycle_motion(
    action_name: Optional[str],
    *,
    elapsed_seconds: float,
    progress: float,
    width: int,
    height: int,
    frame_index: int,
    cycle_seconds: Optional[float] = None,
    cycle_progress: Optional[float] = None,
    travel_start: Optional[float] = None,
    travel_end: Optional[float] = None,
    travel_steps: Optional[int] = None,
) -> Dict[str, float]:
    default_seconds = {
        "walk": 1.0,
        "run": 0.8,
        "fight": 3.0,
        "jump": 2.4,
        "magic": 3.0,
    }.get(action_name or "", 1.0)
    duration = max(0.25, float(cycle_seconds or default_seconds))
    if cycle_progress is not None and action_name not in {"walk", "run"}:
        phase = min(1.0, max(0.0, cycle_progress))
    else:
        phase = (max(0.0, elapsed_seconds) % duration) / duration
    if travel_start is None or travel_end is None:
        if action_name in {"walk", "run"}:
            travel_start, travel_end = -0.22, 0.22
        else:
            travel_start, travel_end = 0.0, 0.0
    stage_progress = (
        min(1.0, max(0.0, cycle_progress))
        if cycle_progress is not None
        else min(1.0, max(0.0, progress))
    )
    travel_progress = _smootherstep(stage_progress)
    if travel_steps and action_name in {"walk", "run"}:
        normalized_steps = max(1, int(travel_steps))
        step_position = stage_progress * normalized_steps
        step_index = min(normalized_steps - 1, int(step_position))
        step_phase = min(1.0, max(0.0, step_position - step_index))
        stance_fraction = 0.35
        step_travel = (
            0.0
            if step_phase <= stance_fraction
            else _smootherstep(
                (step_phase - stance_fraction)
                / (1.0 - stance_fraction)
            )
        )
        travel_progress = (
            1.0
            if stage_progress >= 1.0
            else (step_index + step_travel) / normalized_steps
        )
    stage_x = width * (
        travel_start
        + (travel_end - travel_start) * travel_progress
    )

    if action_name == "fight":
        local_frame = phase * 36.0
        root_x = _interpolate_action_keyframes(
            local_frame,
            [
                (0, 0.0),
                (5, 0.0),
                (11, -12.0),
                (19, 43.0),
                (24, 47.0),
                (29, 14.0),
                (35, 0.0),
            ],
        )
        root_y = _interpolate_action_keyframes(
            local_frame,
            [
                (0, 0.0),
                (5, -1.0),
                (11, 1.5),
                (19, -4.0),
                (24, -2.0),
                (29, 1.0),
                (35, 0.0),
            ],
        )
        scale = _interpolate_action_keyframes(
            local_frame,
            [
                (0, 1.0),
                (5, 1.0),
                (11, 0.98),
                (19, 1.05),
                (24, 1.04),
                (29, 1.01),
                (35, 1.0),
            ],
        )
        return {
            "x": stage_x + root_x * width / 512.0,
            "y": root_y * height / 384.0,
            "angle": 0.0,
            "scale_x": scale,
            "scale_y": scale,
            "shadow_scale": 1.0 + abs(root_x) / 150.0,
            "shadow_opacity": 92.0,
        }

    if action_name == "jump":
        root_y_ratio = _interpolate_action_keyframes(
            phase,
            [
                (0.0, 0.0),
                (0.27, 0.0),
                (0.4, -0.1),
                (0.55, -0.23),
                (0.78, -0.12),
                (1.0, 0.0),
            ],
        )
        lift = abs(root_y_ratio)
        return {
            "x": stage_x,
            "y": root_y_ratio * height,
            "angle": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "shadow_scale": max(0.52, 1.0 - lift * 2.0),
            "shadow_opacity": max(38.0, 92.0 - lift * 210.0),
        }

    if action_name == "magic":
        energy = math.sin(math.pi * phase)
        return {
            "x": stage_x,
            "y": -energy * height * 0.008,
            "angle": 0.0,
            "scale_x": 1.0 + energy * 0.012,
            "scale_y": 1.0 + energy * 0.012,
            "shadow_scale": 1.0 - energy * 0.025,
            "shadow_opacity": 92.0 - energy * 5.0,
        }

    footfall = abs(math.sin(math.tau * phase))
    root_y = (
        -(4.0 if action_name == "walk" else 8.0)
        * footfall
        * height
        / 384.0
    )
    return {
        "x": stage_x,
        "y": root_y,
        "angle": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "shadow_scale": 1.0 - 0.06 * footfall,
        "shadow_opacity": 92.0,
    }


def _prepare_action_segments(
    raw_segments: List[Dict[str, Any]],
    Image,
    np,
    cv2,
    *,
    width: int,
    height: int,
    build_transitions: bool = True,
) -> List[Dict[str, Any]]:
    prepared = []
    for segment in raw_segments:
        action_bytes = segment.get("bytes")
        if not isinstance(action_bytes, bytes) or not action_bytes:
            continue
        try:
            frames, position = _prepare_action_cycle_frames(
                action_bytes,
                Image,
                width=width,
                height=height,
                layout=segment.get("layout"),
                frame_count=segment.get("frame_count"),
            )
        except Exception:
            continue
        if not frames or position is None:
            continue
        if build_transitions:
            transition_frames, samples_per_key = (
                _build_action_transition_frames(
                    frames,
                    Image,
                    np,
                    cv2,
                )
            )
        else:
            transition_frames, samples_per_key = [], 1
        try:
            cycle_seconds = float(segment.get("cycle_seconds") or 0.0)
        except (TypeError, ValueError):
            cycle_seconds = 0.0
        prepared.append(
            {
                "name": str(segment.get("name") or "walk"),
                "frames": frames,
                "transition_frames": transition_frames,
                "samples_per_key": samples_per_key,
                "render_frame_count": len(frames) * samples_per_key,
                "position": position,
                "cycle_seconds": cycle_seconds or None,
            }
        )
    if not build_transitions:
        return prepared
    for index in range(1, len(prepared)):
        previous = prepared[index - 1]
        current = prepared[index]
        previous_end_index = (
            0
            if previous["name"] in {"walk", "run"}
            else len(previous["frames"]) - 1
        )
        if previous["name"] == "jump" and current["name"] == "magic":
            padded, transition_position = _pad_action_frame_sequence(
                (
                    (
                        previous["frames"][previous_end_index],
                        previous["position"],
                    ),
                    (previous["frames"][0], previous["position"]),
                    (current["frames"][0], current["position"]),
                ),
                Image,
            )
            landing_to_ready = _build_optical_transition_pair(
                padded[0],
                padded[1],
                5,
                Image,
                np,
                cv2,
                include_endpoint=True,
            )
            ready_to_cast = _build_optical_transition_pair(
                padded[1],
                padded[2],
                5,
                Image,
                np,
                cv2,
                include_endpoint=True,
            )
            current["entry_transition_frames"] = (
                landing_to_ready[:-1] + ready_to_cast
            )
            current["entry_transition_seconds"] = 0.42
        else:
            first, second, transition_position = _pad_action_frame_pair(
                previous["frames"][previous_end_index],
                previous["position"],
                current["frames"][0],
                current["position"],
                Image,
            )
            current["entry_transition_frames"] = (
                _build_optical_transition_pair(
                    first,
                    second,
                    ACTION_SEGMENT_TRANSITION_SAMPLES,
                    Image,
                    np,
                    cv2,
                    include_endpoint=True,
                )
            )
            current["entry_transition_seconds"] = (
                ACTION_SEGMENT_TRANSITION_SECONDS
            )
        current["entry_transition_position"] = transition_position
    return prepared


def _action_segment_duration_weights(action_names: List[str]) -> List[float]:
    presets = {
        "walk": 1.25,
        "run": 1.0,
        "jump": 0.75,
        "fight": 1.1,
        "magic": 1.25,
    }
    return [presets.get(name, 1.0) for name in action_names]


def _action_segment_boundaries(
    total_frames: int,
    segment_count: int,
    weights: Optional[List[float]] = None,
) -> List[Tuple[int, int]]:
    if segment_count <= 0:
        return []
    normalized_weights = (
        [max(0.01, float(weight)) for weight in weights]
        if weights and len(weights) == segment_count
        else [1.0] * segment_count
    )
    total_weight = sum(normalized_weights)
    boundaries = []
    segment_start = 0
    cumulative = 0.0
    for index, weight in enumerate(normalized_weights):
        cumulative += weight
        if index == segment_count - 1:
            segment_end = total_frames
        else:
            remaining_segments = segment_count - index - 1
            ideal_end = round(total_frames * cumulative / total_weight)
            segment_end = min(
                total_frames - remaining_segments,
                max(segment_start + 1, ideal_end),
            )
        boundaries.append((segment_start, segment_end))
        segment_start = segment_end
    return boundaries


def _resolve_action_segment(
    frame_index: int,
    total_frames: int,
    segment_count: int,
    weights: Optional[List[float]] = None,
) -> Tuple[int, float]:
    if segment_count <= 1:
        return 0, frame_index / max(total_frames - 1, 1)
    boundaries = _action_segment_boundaries(
        total_frames,
        segment_count,
        weights,
    )
    segment_index = next(
        (
            index
            for index, (_, segment_end) in enumerate(boundaries)
            if frame_index < segment_end
        ),
        segment_count - 1,
    )
    segment_start, segment_end = boundaries[segment_index]
    local_progress = (frame_index - segment_start) / max(
        segment_end - segment_start - 1,
        1,
    )
    return segment_index, min(1.0, max(0.0, local_progress))


def _post_entry_action_progress(
    local_progress: float,
    segment_frame_count: int,
    entry_output_frames: int,
) -> float:
    progress = min(1.0, max(0.0, local_progress))
    if entry_output_frames <= 1 or segment_frame_count <= 1:
        return progress
    entry_fraction = min(
        0.9,
        (entry_output_frames - 1) / max(segment_frame_count - 1, 1),
    )
    if progress <= entry_fraction:
        return 0.0
    return min(
        1.0,
        max(0.0, (progress - entry_fraction) / (1.0 - entry_fraction)),
    )


def _build_action_travel_plan(
    action_names: List[str],
    *,
    cinematic_stage: bool,
) -> List[Tuple[float, float]]:
    if not cinematic_stage:
        return [
            _action_travel_bounds(name, index, len(action_names))
            for index, name in enumerate(action_names)
        ]

    cursor = -0.26 if action_names and action_names[0] in {"walk", "run"} else 0.0
    plan = []
    for action_name in action_names:
        start = cursor
        if action_name == "walk":
            cursor = min(0.24, cursor + 0.18)
        elif action_name == "run":
            cursor = min(0.24, cursor + 0.24)
        elif action_name == "jump":
            cursor = min(0.38, cursor + 0.46)
        plan.append((start, cursor))
    return plan


def _action_travel_bounds(
    action_name: Optional[str],
    segment_index: int,
    segment_count: int,
) -> Tuple[float, float]:
    if action_name not in {"walk", "run"}:
        return 0.0, 0.0
    distance = 0.18 if action_name == "run" else 0.22
    if segment_count <= 1:
        return -distance, distance
    if segment_index == 0:
        return -distance, 0.0
    if segment_index == segment_count - 1:
        return 0.0, distance
    return 0.0, 0.0


def _render_layered_frame(
    *,
    background,
    character,
    position: Tuple[int, int],
    Image,
    ImageEnhance,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
    motion_preset: str,
    elapsed_seconds: Optional[float] = None,
    action_motion: Optional[Dict[str, float]] = None,
    action_name: Optional[str] = None,
    action_progress: float = 0.0,
    story_stage: Optional[Dict[str, Any]] = None,
    ImageDraw=None,
    ImageFilter=None,
    cinematic_state: Optional[Dict[str, Any]] = None,
):
    staged_background = compose_story_stage_background(
        background,
        story_stage,
        action_name=action_name,
        action_progress=action_progress,
        Image=Image,
        ImageDraw=ImageDraw,
        ImageFilter=ImageFilter,
    )
    scene_frame = staged_background.copy().convert("RGBA")
    motion = _character_motion(
        preset=motion_preset,
        progress=progress,
        width=width,
        height=height,
        motion_strength=motion_strength,
        elapsed_seconds=elapsed_seconds,
    )
    if action_motion is not None:
        motion = action_motion
    scaled_width = max(1, round(character.width * motion["scale_x"]))
    scaled_height = max(1, round(character.height * motion["scale_y"]))
    animated = character.resize(
        (scaled_width, scaled_height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    animated = animated.rotate(
        motion["angle"],
        resample=getattr(Image, "Resampling", Image).BICUBIC,
        expand=True,
    )

    base_x, base_y = position
    base_center_x = base_x + character.width // 2
    base_feet_y = base_y + character.height
    character_x = round(base_center_x - animated.width / 2 + motion["x"])
    character_y = round(base_feet_y - animated.height + motion["y"])
    shadow = build_character_shadow(
        scene_frame.size,
        animated.size,
        (character_x, character_y),
        opacity=round(motion["shadow_opacity"]),
        scale=motion["shadow_scale"],
    )
    scene_frame.alpha_composite(shadow)
    trail_strength = min(
        0.35,
        max(
            0.0,
            float(
                (cinematic_state or {}).get(
                    "motion_trail_strength",
                    0.0,
                )
                or 0.0
            ),
        ),
    )
    if trail_strength > 0.0:
        trail_x = round(
            float((cinematic_state or {}).get("trail_x_ratio", 0.0) or 0.0)
            * width
        )
        trail_y = round(
            float((cinematic_state or {}).get("trail_y_ratio", 0.0) or 0.0)
            * height
        )
        for distance, alpha_scale in ((2, 0.34), (1, 0.56)):
            ghost = animated.copy()
            ghost_alpha = ghost.getchannel("A").point(
                lambda alpha, factor=trail_strength * alpha_scale: round(
                    alpha * factor
                )
            )
            ghost.putalpha(ghost_alpha)
            if ImageFilter is not None:
                ghost = ghost.filter(ImageFilter.GaussianBlur(0.7))
            scene_frame.alpha_composite(
                ghost,
                (
                    character_x + trail_x * distance,
                    character_y + trail_y * distance,
                ),
            )
    scene_frame.alpha_composite(animated, (character_x, character_y))
    scene_frame = composite_story_action_effects(
        scene_frame,
        story_stage,
        action_name=action_name,
        action_progress=action_progress,
        character_box=(
            character_x,
            character_y,
            animated.width,
            animated.height,
        ),
        feet_center=(
            character_x + animated.width // 2,
            character_y + animated.height,
        ),
        camera_progress=None,
        motion_strength=motion_strength,
        Image=Image,
        ImageDraw=ImageDraw,
        ImageFilter=ImageFilter,
    )
    if cinematic_state is not None:
        frame = apply_cinematic_camera(
            scene_frame.convert("RGB"),
            cinematic_state,
            Image,
            ImageEnhance,
        )
        return apply_cinematic_foreground(
            frame,
            cinematic_state,
            Image,
            ImageDraw,
            ImageFilter,
        )
    return _render_frame(
        source_image=scene_frame.convert("RGB"),
        Image=Image,
        ImageEnhance=ImageEnhance,
        ImageOps=ImageOps,
        width=width,
        height=height,
        progress=progress,
        motion_strength=max(1, motion_strength // 2),
    )


def _generate_local_video_bytes(
    *,
    image_bytes: bytes,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: int,
    motion_strength: int,
    quality_steps: int,
    story_text: str,
    background_bytes: Optional[bytes] = None,
    character_layer_bytes: Optional[bytes] = None,
    action_cycle_bytes: Optional[bytes] = None,
    action_cycle_name: Optional[str] = None,
    action_cycle_layout: Optional[str] = None,
    action_cycle_frame_count: Optional[int] = None,
    action_cycle_segments: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bytes, str]:
    (
        imageio,
        np,
        Image,
        ImageEnhance,
        ImageOps,
        cv2,
        ImageDraw,
        ImageFilter,
    ) = _load_video_dependencies()
    width = _even_dimension(width)
    height = _even_dimension(height)
    frame_rate = min(max(int(frame_rate), 6), 30)
    total_frames = _normalize_frame_count(num_frames, frame_rate)
    render_scale = _quality_render_scale(quality_steps)
    render_width = _even_dimension(round(width * render_scale))
    render_height = _even_dimension(round(height * render_scale))

    layered_scene = None
    if background_bytes and character_layer_bytes:
        try:
            layered_scene = prepare_story_scene_layers(
                background_bytes,
                character_layer_bytes,
                width=render_width,
                height=render_height,
            )
        except Exception:
            layered_scene = None

    if layered_scene is None:
        try:
            source_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise HfMediaError(
                "Generated image bytes could not be opened for video rendering."
            ) from exc
    motion_preset = select_motion_preset(story_text)
    raw_action_segments = list(action_cycle_segments or [])
    if not raw_action_segments and action_cycle_bytes:
        raw_action_segments.append(
            {
                "bytes": action_cycle_bytes,
                "name": action_cycle_name,
                "layout": action_cycle_layout,
                "frame_count": action_cycle_frame_count,
            }
        )
    raw_action_names = [
        str(segment.get("name") or "").strip().lower()
        for segment in raw_action_segments
    ]
    cinematic_candidate = supports_cinematic_animatic(
        raw_action_names,
        supports_story_stage(raw_action_names, story_text),
    )
    prepared_action_segments = (
        _prepare_action_segments(
            raw_action_segments,
            Image,
            np,
            cv2,
            width=render_width,
            height=render_height,
            build_transitions=True,
        )
        if layered_scene is not None
        else []
    )
    prepared_action_names = [
        segment["name"] for segment in prepared_action_segments
    ]
    segment_weights = _action_segment_duration_weights(prepared_action_names)
    segment_boundaries = _action_segment_boundaries(
        total_frames,
        len(prepared_action_segments),
        segment_weights,
    )
    story_stage = prepare_story_stage(
        prepared_action_names,
        Image,
        width=render_width,
        height=render_height,
        story_text=story_text,
    )
    cinematic_animatic = supports_cinematic_animatic(
        prepared_action_names,
        story_stage is not None,
    )
    if cinematic_candidate and not cinematic_animatic:
        prepared_action_segments = _prepare_action_segments(
            raw_action_segments,
            Image,
            np,
            cv2,
            width=render_width,
            height=render_height,
            build_transitions=True,
        )
        prepared_action_names = [
            segment["name"] for segment in prepared_action_segments
        ]
        segment_weights = _action_segment_duration_weights(
            prepared_action_names
        )
        segment_boundaries = _action_segment_boundaries(
            total_frames,
            len(prepared_action_segments),
            segment_weights,
        )
        story_stage = prepare_story_stage(
            prepared_action_names,
            Image,
            width=render_width,
            height=render_height,
            story_text=story_text,
        )
    cinematic_segments = {
        segment["name"]: segment for segment in prepared_action_segments
    }
    cinematic_frame_counts = {
        name: len(segment["frames"])
        for name, segment in cinematic_segments.items()
    }
    travel_plan = _build_action_travel_plan(
        prepared_action_names,
        cinematic_stage=story_stage is not None,
    )

    with tempfile.TemporaryDirectory(prefix="fairytale_video_") as temp_dir:
        output_path = Path(temp_dir) / "scene.mp4"
        writer = imageio.get_writer(
            str(output_path),
            fps=frame_rate,
            codec="libx264",
            quality=8,
            macro_block_size=16,
            ffmpeg_log_level="error",
            output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )
        try:
            for index in range(total_frames):
                progress = index / max(total_frames - 1, 1)
                action_motion = None
                cinematic_state = None
                frame_action_name = None
                frame_action_progress = progress
                if layered_scene is not None:
                    background, character, position = layered_scene
                    if cinematic_animatic:
                        cinematic_state = resolve_cinematic_shot(
                            index,
                            total_frames,
                            frame_rate,
                            cinematic_frame_counts,
                        )
                        segment = cinematic_segments[
                            cinematic_state["action_name"]
                        ]
                        pose_index = min(
                            len(segment["frames"]) - 1,
                            max(0, int(cinematic_state["pose_index"])),
                        )
                        character = segment["frames"][pose_index]
                        position = segment["position"]
                        entry_transition_frames = (
                            segment.get("entry_transition_frames") or []
                        )
                        entry_transition_index = None
                        for look_back in range(
                            1,
                            min(
                                len(entry_transition_frames) + 1,
                                index + 1,
                            ),
                        ):
                            previous_state = resolve_cinematic_shot(
                                index - look_back,
                                total_frames,
                                frame_rate,
                                cinematic_frame_counts,
                            )
                            if (
                                previous_state["action_name"]
                                != cinematic_state["action_name"]
                            ):
                                entry_transition_index = look_back - 1
                                break
                        if entry_transition_index is not None:
                            character = entry_transition_frames[
                                entry_transition_index
                            ]
                            position = segment.get(
                                "entry_transition_position",
                                position,
                            )
                        else:
                            transition_frames = (
                                segment.get("transition_frames") or []
                            )
                            if transition_frames:
                                for look_ahead in range(
                                    CINEMATIC_POSE_TRANSITION_FRAMES,
                                    0,
                                    -1,
                                ):
                                    future_index = min(
                                        total_frames - 1,
                                        index + look_ahead,
                                    )
                                    future_state = resolve_cinematic_shot(
                                        future_index,
                                        total_frames,
                                        frame_rate,
                                        cinematic_frame_counts,
                                    )
                                    future_pose_index = int(
                                        future_state["pose_index"]
                                    )
                                    expected_next_pose = (
                                        pose_index + 1
                                    ) % len(segment["frames"])
                                    if (
                                        future_state["action_name"]
                                        != cinematic_state["action_name"]
                                        or future_pose_index != expected_next_pose
                                    ):
                                        continue
                                    samples = transition_frames[pose_index]
                                    transition_index = min(
                                        len(samples) - 1,
                                        CINEMATIC_POSE_TRANSITION_FRAMES
                                        - look_ahead
                                        + 1,
                                    )
                                    character = samples[transition_index]
                                    break
                        frame_action_name = cinematic_state["action_name"]
                        frame_action_progress = cinematic_state[
                            "action_progress"
                        ]
                        action_motion = {
                            "x": cinematic_state["x_ratio"] * render_width,
                            "y": cinematic_state["y_ratio"] * render_height,
                            "angle": 0.0,
                            "scale_x": cinematic_state["scale_x"],
                            "scale_y": cinematic_state["scale_y"],
                            "shadow_scale": cinematic_state["shadow_scale"],
                            "shadow_opacity": (
                                cinematic_state["shadow_opacity"] * 255.0
                            ),
                        }
                    elif prepared_action_segments:
                        segment_index, local_progress = _resolve_action_segment(
                            index,
                            total_frames,
                            len(prepared_action_segments),
                            segment_weights,
                        )
                        segment = prepared_action_segments[segment_index]
                        action_name = segment["name"]
                        frame_action_name = action_name
                        frame_action_progress = local_progress
                        segment_start, segment_end = segment_boundaries[
                            segment_index
                        ]
                        segment_frame_count = max(
                            1,
                            segment_end - segment_start,
                        )
                        segment_duration = segment_frame_count / frame_rate
                        frame_cycle_seconds = segment["cycle_seconds"]
                        if (
                            story_stage is not None
                            and action_name in {"walk", "run"}
                        ):
                            gait_cycles = 2 if action_name == "walk" else 3
                            frame_cycle_seconds = (
                                segment_duration / gait_cycles
                            )
                        entry_frames = (
                            segment.get("entry_transition_frames") or []
                        )
                        entry_output_frames = max(
                            2,
                            round(
                                float(
                                    segment.get(
                                        "entry_transition_seconds",
                                        ACTION_SEGMENT_TRANSITION_SECONDS,
                                    )
                                )
                                * frame_rate
                            ),
                        )
                        pose_progress = _post_entry_action_progress(
                            local_progress,
                            segment_frame_count,
                            entry_output_frames if entry_frames else 0,
                        )
                        frame_action_progress = pose_progress
                        local_elapsed_seconds = (
                            pose_progress * segment_duration
                        )
                        cycle_progress = (
                            pose_progress
                            if len(prepared_action_segments) > 1
                            else None
                        )
                        (
                            action_index,
                            next_action_index,
                            action_pose_progress,
                        ) = _action_cycle_frame_sample(
                            action_name,
                            local_elapsed_seconds,
                            len(segment["frames"]),
                            cycle_seconds=frame_cycle_seconds,
                            cycle_progress=cycle_progress,
                            frame_rate=frame_rate,
                        )
                        character = segment["frames"][action_index]
                        if next_action_index != action_index:
                            transition_index = min(
                                segment["samples_per_key"] - 1,
                                int(
                                    action_pose_progress
                                    * segment["samples_per_key"]
                                ),
                            )
                            character = segment["transition_frames"][
                                action_index
                            ][transition_index]
                        position = segment["position"]
                        local_frame_index = round(
                            local_progress * max(segment_frame_count - 1, 1)
                        )
                        if entry_frames and local_frame_index < entry_output_frames:
                            entry_index = min(
                                len(entry_frames) - 1,
                                round(
                                    local_frame_index
                                    / max(entry_output_frames - 1, 1)
                                    * (len(entry_frames) - 1)
                                ),
                            )
                            character = entry_frames[entry_index]
                            position = segment["entry_transition_position"]
                        travel_start, travel_end = travel_plan[segment_index]
                        action_motion = _action_cycle_motion(
                            action_name,
                            elapsed_seconds=local_elapsed_seconds,
                            progress=pose_progress,
                            width=render_width,
                            height=render_height,
                            frame_index=action_index,
                            cycle_seconds=frame_cycle_seconds,
                            cycle_progress=cycle_progress,
                            travel_start=travel_start,
                            travel_end=travel_end,
                            travel_steps=(
                                4
                                if story_stage is not None
                                and action_name == "walk"
                                else (
                                    3
                                    if story_stage is not None
                                    and action_name == "run"
                                    else None
                                )
                            ),
                        )
                    frame = _render_layered_frame(
                        background=background,
                        character=character,
                        position=position,
                        Image=Image,
                        ImageDraw=ImageDraw,
                        ImageEnhance=ImageEnhance,
                        ImageFilter=ImageFilter,
                        ImageOps=ImageOps,
                        width=render_width,
                        height=render_height,
                        progress=progress,
                        motion_strength=motion_strength,
                        motion_preset=motion_preset,
                        elapsed_seconds=index / frame_rate,
                        action_motion=action_motion,
                        action_name=frame_action_name,
                        action_progress=frame_action_progress,
                        story_stage=story_stage,
                        cinematic_state=cinematic_state,
                    )
                    if cinematic_state is not None:
                        frame = apply_cinematic_cut_effect(
                            frame,
                            cinematic_state,
                            Image,
                            ImageDraw,
                            ImageFilter,
                        )
                else:
                    frame = _render_frame(
                        source_image=source_image,
                        Image=Image,
                        ImageEnhance=ImageEnhance,
                        ImageOps=ImageOps,
                        width=render_width,
                        height=render_height,
                        progress=progress,
                        motion_strength=motion_strength,
                    )
                if frame.size != (width, height):
                    frame = frame.resize(
                        (width, height),
                        getattr(Image, "Resampling", Image).LANCZOS,
                    )
                writer.append_data(np.asarray(frame, dtype=np.uint8))
        finally:
            writer.close()

        video_bytes = output_path.read_bytes()
        if not video_bytes:
            raise HfMediaError("Local video renderer returned an empty MP4 file.")
        if cinematic_animatic:
            animation_mode = CINEMATIC_ANIMATION_MODE
        elif len(prepared_action_segments) > 1:
            animation_mode = "profile_action_sequence"
        elif prepared_action_segments:
            animation_mode = "profile_action_cycle"
        elif layered_scene is not None:
            animation_mode = "identity_safe_character_parallax"
        else:
            animation_mode = "ken_burns"
        return video_bytes, animation_mode


async def generate_hf_fairytale_video(
    *,
    image_bytes: bytes,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = 512,
    height: int = 384,
    num_frames: int = 96,
    steps: int = 12,
    seed: Optional[int] = None,
    frame_rate: Optional[int] = None,
    background_bytes: Optional[bytes] = None,
    character_layer_bytes: Optional[bytes] = None,
    action_cycle_bytes: Optional[bytes] = None,
    action_cycle_name: Optional[str] = None,
    action_cycle_layout: Optional[str] = None,
    action_cycle_frame_count: Optional[int] = None,
    action_cycle_segments: Optional[List[Dict[str, Any]]] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    if not image_bytes:
        raise HfMediaError("image_bytes is empty.")

    prompt = build_fairytale_video_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
    )
    normalized_frame_rate = frame_rate or LOCAL_VIDEO_FRAME_RATE
    normalized_frames = _normalize_frame_count(num_frames, normalized_frame_rate)
    normalized_timeout = min(
        LOCAL_VIDEO_TIMEOUT_SECONDS,
        max(5.0, float(timeout_seconds or LOCAL_VIDEO_TIMEOUT_SECONDS)),
    )
    quality_steps = min(max(int(steps), 2), 16)
    motion_strength = min(5, max(3, round(quality_steps / 3)))

    try:
        video_bytes, animation_mode = await asyncio.wait_for(
            asyncio.to_thread(
                _generate_local_video_bytes,
                image_bytes=image_bytes,
                width=width,
                height=height,
                num_frames=normalized_frames,
                frame_rate=normalized_frame_rate,
                motion_strength=motion_strength,
                quality_steps=quality_steps,
                story_text=story_text,
                background_bytes=background_bytes,
                character_layer_bytes=character_layer_bytes,
                action_cycle_bytes=action_cycle_bytes,
                action_cycle_name=action_cycle_name,
                action_cycle_layout=action_cycle_layout,
                action_cycle_frame_count=action_cycle_frame_count,
                action_cycle_segments=action_cycle_segments,
            ),
            timeout=normalized_timeout,
        )
    except asyncio.TimeoutError as exc:
        raise HfMediaError(
            f"Local video generation exceeded {normalized_timeout:g} seconds."
        ) from exc
    motion_preset = select_motion_preset(story_text)
    normalized_rate = min(max(int(normalized_frame_rate), 6), 30)
    action_cycle_names = [
        str(segment.get("name"))
        for segment in (action_cycle_segments or [])
        if segment.get("name")
    ]
    if not action_cycle_names and action_cycle_name:
        action_cycle_names = [action_cycle_name]
    character_animation_modes = {
        "identity_safe_character_parallax",
        "profile_action_cycle",
        "profile_action_sequence",
        CINEMATIC_ANIMATION_MODE,
    }
    action_animation_modes = {
        "profile_action_cycle",
        "profile_action_sequence",
        CINEMATIC_ANIMATION_MODE,
    }

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
            "frame_rate": normalized_rate,
            "duration_seconds": round(normalized_frames / normalized_rate, 2),
            "max_duration_seconds": LOCAL_VIDEO_MAX_DURATION_SECONDS,
            "timeout_seconds": normalized_timeout,
            "motion_strength": motion_strength,
            "quality_steps": quality_steps,
            "render_scale": _quality_render_scale(quality_steps),
            "motion_preset": motion_preset,
            "animation_mode": animation_mode,
            "character_motion": animation_mode in character_animation_modes,
            "character_identity_locked": (
                animation_mode in character_animation_modes
            ),
            "action_cycle_name": (
                action_cycle_names[0]
                if animation_mode in action_animation_modes
                and action_cycle_names
                else None
            ),
            "action_cycle_names": (
                action_cycle_names
                if animation_mode in action_animation_modes
                else []
            ),
            "action_segment_count": (
                len(action_cycle_names)
                if animation_mode in action_animation_modes
                else 0
            ),
            "action_cycle_frame_count": (
                (
                    action_cycle_segments[0].get("frame_count")
                    if action_cycle_segments
                    else action_cycle_frame_count
                )
                if animation_mode in action_animation_modes
                else None
            ),
            "transition_mode": (
                "castle-directed-optical-pose-inbetweens"
                if animation_mode == CINEMATIC_ANIMATION_MODE
                else (
                    "grounded-landing-recovery-root-aligned-entry"
                    if animation_mode == "profile_action_sequence"
                    else None
                )
            ),
            "frame_interpolation": (
                "character-layer-optical-flow"
                if animation_mode == CINEMATIC_ANIMATION_MODE
                else (
                    "character-layer-optical-flow"
                    if animation_mode in action_animation_modes
                    else None
                )
            ),
            "inbetween_frames_per_transition": (
                CINEMATIC_POSE_TRANSITION_FRAMES
                if animation_mode == CINEMATIC_ANIMATION_MODE
                else (
                    math.ceil(
                        ACTION_RENDER_FRAME_TARGET
                        / max(
                            1,
                            int(
                                (
                                    action_cycle_segments[0].get("frame_count")
                                    if action_cycle_segments
                                    else action_cycle_frame_count
                                )
                                or 1
                            ),
                        )
                    )
                    - 1
                )
                if animation_mode in action_animation_modes
                else 0
            ),
            "action_cycle_render_frame_count": (
                ACTION_RENDER_FRAME_TARGET
                if animation_mode
                in {"profile_action_cycle", "profile_action_sequence"}
                else None
            ),
            "segment_duration_weights": (
                _action_segment_duration_weights(action_cycle_names)
                if animation_mode == "profile_action_sequence"
                else []
            ),
            "cinematic_shot_count": (
                11 if animation_mode == CINEMATIC_ANIMATION_MODE else 0
            ),
            "story_stage": (
                STAGE_ID
                if supports_story_stage(action_cycle_names, story_text)
                else None
            ),
            "narrative_arc": (
                "castle-bound-approach-jump-unlock"
                if supports_story_stage(action_cycle_names, story_text)
                else None
            ),
            "seed": seed,
        },
    }
