"""Pure timeline helpers for an intentional storybook cinematic animatic.

This module does not interpolate character poses. Each shot chooses a fixed
pose index while root motion, jump height, and simple cut effects remain
continuous over time.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


ANIMATION_MODE = "cinematic_storyboard_v2"

_DEFAULT_FRAME_COUNTS = {
    "walk": 6,
    "run": 6,
    "jump": 6,
    "magic": 6,
}

_SHOT_LAYOUT = (
    ("approach", 0.00, 0.21, "approach"),
    ("notice", 0.21, 0.26, "approach"),
    ("crouch", 0.26, 0.32, "jump"),
    ("takeoff", 0.32, 0.38, "jump"),
    ("flight", 0.38, 0.44, "jump"),
    ("apex", 0.44, 0.50, "jump"),
    ("landing", 0.50, 0.57, "jump"),
    ("recovery", 0.57, 0.63, "jump"),
    ("charge", 0.63, 0.74, "magic"),
    ("release", 0.74, 0.85, "magic"),
    ("resolution", 0.85, 1.00, "magic"),
)

_APPROACH_ALIASES = {"walk", "walking", "run", "running"}
_JUMP_ALIASES = {"jump", "jumping", "leap", "hop"}
_MAGIC_ALIASES = {"magic", "cast", "casting", "casting_magic", "spell"}


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * _clamp(progress)


def _smoothstep(progress: float) -> float:
    t = _clamp(progress)
    return t * t * (3.0 - 2.0 * t)


def _canonical_action(name: Any) -> str:
    normalized = str(name or "").strip().lower().replace("-", "_")
    if normalized in {"run", "running", "runs", "sprint", "dash"}:
        return "run"
    if normalized in {"walk", "walking", "walks", "journey", "travel"}:
        return "walk"
    if normalized in _JUMP_ALIASES or normalized in {"jumps"}:
        return "jump"
    if normalized in _MAGIC_ALIASES or normalized in {"casts"}:
        return "magic"
    return normalized


def supports_cinematic_animatic(
    action_names: Iterable[Any],
    has_story_stage: bool,
) -> bool:
    """Return True for a story stage that follows approach -> jump -> magic."""

    if not has_story_stage:
        return False
    normalized = [_canonical_action(name) for name in action_names]
    if len(normalized) != 3:
        return False
    return (
        normalized[0] in {"walk", "run"}
        and normalized[1] == "jump"
        and normalized[2] == "magic"
    )


def _normalized_frame_counts(
    action_frame_counts: Optional[Mapping[str, Any]],
) -> Dict[str, int]:
    counts = dict(_DEFAULT_FRAME_COUNTS)
    if not action_frame_counts:
        return counts
    for key, value in action_frame_counts.items():
        normalized_key = _canonical_action(key)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            counts[normalized_key] = parsed
    if "run" not in counts and "walk" in counts:
        counts["run"] = counts["walk"]
    return counts


def _resolve_approach_action(
    action_frame_counts: Optional[Mapping[str, Any]],
) -> str:
    if not action_frame_counts:
        return "walk"
    normalized_keys = {_canonical_action(key) for key in action_frame_counts.keys()}
    if "walk" in normalized_keys:
        return "walk"
    if "run" in normalized_keys:
        return "run"
    if normalized_keys & _APPROACH_ALIASES:
        return "walk"
    return "walk"


def _pose_index(frame_count: int, preferred_index: int) -> int:
    if frame_count <= 1:
        return 0
    return max(0, min(frame_count - 1, preferred_index))


def _shot_for_phase(phase: float) -> Dict[str, Any]:
    for shot_id, start, end, action_group in _SHOT_LAYOUT:
        if phase <= end or math.isclose(phase, end):
            span = max(end - start, 1e-9)
            return {
                "id": shot_id,
                "start": start,
                "end": end,
                "local_progress": _clamp((phase - start) / span),
                "action_group": action_group,
            }
    last_id, start, end, action_group = _SHOT_LAYOUT[-1]
    return {
        "id": last_id,
        "start": start,
        "end": end,
        "local_progress": 1.0,
        "action_group": action_group,
    }


def _approach_pose(
    action_name: str,
    local_progress: float,
    frame_count: int,
) -> int:
    if frame_count <= 1:
        return 0
    cycle_count = 2.5 if action_name == "run" else 2.0
    pose_position = min(0.999999, _clamp(local_progress)) * frame_count * cycle_count
    return int(pose_position) % frame_count


def _stepped_approach_progress(
    local_progress: float,
    action_name: str,
    frame_count: int,
) -> float:
    cycle_count = 2.5 if action_name == "run" else 2.0
    step_count = max(4, round(frame_count * cycle_count))
    progress = _clamp(local_progress)
    if progress >= 1.0:
        return 1.0
    step_position = progress * step_count
    step_index = min(step_count - 1, int(step_position))
    within_step = step_position - step_index
    swing_progress = _smoothstep(min(1.0, within_step / 0.42))
    return (step_index + swing_progress) / step_count


def _jump_pose(
    shot_id: str,
    frame_count: int,
    local_progress: float,
) -> int:
    if frame_count >= 9:
        if shot_id == "crouch":
            if local_progress < 0.24:
                return _pose_index(frame_count, 1)
            if local_progress < 0.58:
                return _pose_index(frame_count, 2)
            return _pose_index(frame_count, 3)
        if shot_id == "takeoff":
            return _pose_index(frame_count, 3 if local_progress < 0.42 else 4)
        if shot_id == "flight":
            return _pose_index(frame_count, 5 if local_progress < 0.62 else 6)
        if shot_id == "apex":
            return _pose_index(frame_count, 6)
        if shot_id == "landing":
            return _pose_index(frame_count, 7 if local_progress < 0.56 else 8)
        if shot_id == "recovery":
            return _pose_index(frame_count, 8 if local_progress < 0.54 else 0)
        return _pose_index(frame_count, 0)
    if shot_id == "crouch":
        return _pose_index(frame_count, 0 if local_progress < 0.38 else 1)
    if shot_id == "takeoff":
        return _pose_index(frame_count, 1 if local_progress < 0.16 else 2)
    if shot_id == "flight":
        return _pose_index(frame_count, 2 if local_progress < 0.68 else 3)
    if shot_id == "apex":
        return _pose_index(frame_count, 3)
    if shot_id == "landing":
        return _pose_index(frame_count, 4 if local_progress < 0.62 else 5)
    if shot_id == "recovery":
        return _pose_index(frame_count, 5 if local_progress < 0.46 else 0)
    return _pose_index(frame_count, 0)


def _magic_pose(shot_id: str, frame_count: int, local_progress: float) -> int:
    if frame_count >= 9:
        if shot_id == "charge":
            if local_progress < 0.12:
                return _pose_index(frame_count, 0)
            if local_progress < 0.25:
                return _pose_index(frame_count, 1)
            if local_progress < 0.43:
                return _pose_index(frame_count, 2)
            if local_progress < 0.66:
                return _pose_index(frame_count, 3)
            if local_progress < 0.86:
                return _pose_index(frame_count, 4)
            return _pose_index(frame_count, 5)
        if shot_id == "release":
            if local_progress < 0.18:
                return _pose_index(frame_count, 5)
            if local_progress < 0.56:
                return _pose_index(frame_count, 6)
            if local_progress < 0.84:
                return _pose_index(frame_count, 7)
            return _pose_index(frame_count, 8)
        return _pose_index(frame_count, 8)
    if shot_id == "charge":
        if local_progress < 0.20:
            return _pose_index(frame_count, 0)
        return _pose_index(frame_count, 1 if local_progress < 0.58 else 2)
    if shot_id == "release":
        if local_progress < 0.18:
            return _pose_index(frame_count, 2)
        return _pose_index(frame_count, 3 if local_progress < 0.60 else 4)
    return _pose_index(frame_count, frame_count - 1)


def _jump_world_state(jump_progress: float) -> Dict[str, float]:
    travel = _smoothstep(jump_progress)
    lift = math.sin(math.pi * _clamp(jump_progress))
    return {
        "x_ratio": _lerp(-0.03, 0.31, travel),
        "y_ratio": -0.26 * lift,
        "shadow_scale": _lerp(1.0, 0.62, lift),
        "shadow_opacity": _lerp(0.25, 0.14, lift),
    }


def _camera_state(
    shot_id: str,
    local_progress: float,
) -> Dict[str, float]:
    camera_progress = (
        min(1.0, local_progress / 0.72)
        if shot_id == "resolution"
        else local_progress
    )
    progress = _smoothstep(camera_progress)
    camera_by_shot = {
        "approach": (1.02, 1.07, 0.46, 0.52, 0.51, 0.51),
        "notice": (1.08, 1.13, 0.51, 0.53, 0.50, 0.48),
        "crouch": (1.08, 1.10, 0.53, 0.55, 0.54, 0.56),
        "takeoff": (1.08, 1.03, 0.55, 0.59, 0.55, 0.51),
        "flight": (1.03, 1.00, 0.58, 0.61, 0.51, 0.48),
        "apex": (1.00, 1.00, 0.61, 0.62, 0.47, 0.47),
        "landing": (1.02, 1.04, 0.62, 0.63, 0.53, 0.55),
        "recovery": (1.04, 1.06, 0.62, 0.61, 0.54, 0.52),
        "charge": (1.06, 1.09, 0.61, 0.60, 0.51, 0.50),
        "release": (1.10, 1.08, 0.60, 0.59, 0.50, 0.50),
        "resolution": (1.06, 1.02, 0.59, 0.58, 0.50, 0.50),
    }
    (
        zoom_start,
        zoom_end,
        center_x_start,
        center_x_end,
        center_y_start,
        center_y_end,
    ) = camera_by_shot.get(
        shot_id,
        (1.04, 1.06, 0.5, 0.5, 0.5, 0.5),
    )
    zoom = _lerp(zoom_start, zoom_end, progress)
    shake_x = 0.0
    shake_y = 0.0
    impact_strength = 0.0
    if shot_id == "landing":
        impact_strength = max(0.0, 1.0 - abs(local_progress - 0.64) / 0.18)
        impact_phase = max(0.0, local_progress - 0.48)
        shake_x = math.sin(impact_phase * math.tau * 9.0) * 0.004 * impact_strength
        shake_y = math.sin(impact_phase * math.tau * 13.0) * 0.012 * impact_strength
        zoom += 0.025 * impact_strength
    elif shot_id == "release":
        impact_strength = max(0.0, 1.0 - abs(local_progress - 0.76) / 0.16)
        impact_phase = max(0.0, local_progress - 0.58)
        shake_x = math.sin(impact_phase * math.tau * 10.0) * 0.007 * impact_strength
        shake_y = math.sin(impact_phase * math.tau * 7.0) * 0.004 * impact_strength
        zoom += 0.018 * impact_strength

    return {
        "camera_zoom": zoom,
        "camera_center_x": _lerp(center_x_start, center_x_end, progress),
        "camera_center_y": _lerp(center_y_start, center_y_end, progress),
        "camera_shake_x": shake_x,
        "camera_shake_y": shake_y,
        "impact_strength": impact_strength,
    }


def _motion_trail_state(shot_id: str, local_progress: float) -> Dict[str, float]:
    if shot_id in {"takeoff", "flight"}:
        envelope = math.sin(math.pi * _clamp(local_progress))
        return {
            "motion_trail_strength": 0.20 * envelope,
            "trail_x_ratio": -0.018,
            "trail_y_ratio": 0.009,
        }
    if shot_id == "release":
        envelope = max(0.0, 1.0 - abs(local_progress - 0.18) / 0.18)
        return {
            "motion_trail_strength": 0.24 * envelope,
            "trail_x_ratio": -0.012,
            "trail_y_ratio": 0.0,
        }
    return {
        "motion_trail_strength": 0.0,
        "trail_x_ratio": 0.0,
        "trail_y_ratio": 0.0,
    }


def resolve_cinematic_shot(
    frame_index: int,
    total_frames: int,
    frame_rate: float,
    action_frame_counts: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Resolve the fixed-pose shot state for one output frame.

    The returned values are normalized ratios that a renderer can translate
    into scene coordinates. `x_ratio` and `y_ratio` follow the same
    center-relative style used by the existing video provider.
    """

    safe_total_frames = max(1, int(total_frames or 1))
    safe_frame_index = max(0, min(safe_total_frames - 1, int(frame_index or 0)))
    phase = (
        safe_frame_index / max(safe_total_frames - 1, 1)
        if safe_total_frames > 1
        else 0.0
    )
    counts = _normalized_frame_counts(action_frame_counts)
    approach_action = _resolve_approach_action(action_frame_counts)
    shot = _shot_for_phase(phase)
    shot_id = str(shot["id"])
    local_progress = float(shot["local_progress"])
    cut_strength = (
        max(0.0, 1.0 - abs(local_progress - 0.76) / 0.075) * 0.78
        if shot_id == "release"
        else 0.0
    )

    if shot["action_group"] == "approach":
        frame_count = counts.get(approach_action, counts["walk"])
        gait_cycles = 2.5 if approach_action == "run" else 2.0
        walk_wave = math.sin(math.tau * local_progress * gait_cycles)
        approach_progress = (
            _lerp(0.04, 0.82, local_progress)
            if shot_id == "approach"
            else _lerp(0.82, 0.98, local_progress)
        )
        state = {
            "action_name": approach_action,
            "action_progress": approach_progress,
            "pose_index": (
                _approach_pose(approach_action, local_progress, frame_count)
                if shot_id == "approach"
                else _pose_index(frame_count, min(frame_count - 1, 1))
            ),
            "x_ratio": (
                _lerp(
                    -0.28,
                    -0.04,
                    _stepped_approach_progress(
                        local_progress,
                        approach_action,
                        frame_count,
                    ),
                )
                if shot_id == "approach"
                else -0.04
            ),
            "y_ratio": (
                -0.010 * walk_wave
                if shot_id == "approach"
                else 0.006 * _smoothstep(local_progress)
            ),
            "scale_x": 1.0,
            "scale_y": 1.0 + (0.008 * walk_wave if shot_id == "approach" else -0.02 * _smoothstep(local_progress)),
            "shadow_scale": 1.0,
            "shadow_opacity": 0.25,
        }
    elif shot["action_group"] == "jump":
        frame_count = counts.get("jump", _DEFAULT_FRAME_COUNTS["jump"])
        if shot_id == "crouch":
            jump_progress = _lerp(0.00, 0.14, local_progress)
            world = {
                "x_ratio": _lerp(-0.04, -0.03, _smoothstep(local_progress)),
                "y_ratio": 0.018 * _smoothstep(local_progress),
                "shadow_scale": 1.03,
                "shadow_opacity": 0.28,
            }
            scale_x = _lerp(0.96, 1.0, _smoothstep(local_progress))
            scale_y = _lerp(0.96, 0.90, _smoothstep(local_progress))
        elif shot_id == "takeoff":
            launch_progress = _smoothstep(
                max(0.0, (local_progress - 0.18) / 0.82)
            )
            jump_progress = _lerp(0.0, 0.28, launch_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(0.98, 0.93, _smoothstep(local_progress))
            scale_y = _lerp(0.92, 0.99, _smoothstep(local_progress))
        elif shot_id == "flight":
            jump_progress = _lerp(0.28, 0.50, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(0.93, 0.91, _smoothstep(local_progress))
            scale_y = _lerp(0.99, 0.95, _smoothstep(local_progress))
        elif shot_id == "apex":
            jump_progress = _lerp(0.50, 0.72, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = 0.91
            scale_y = 0.95
        elif shot_id == "landing":
            jump_progress = _lerp(0.72, 1.0, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(0.94, 0.96, _smoothstep(local_progress))
            scale_y = _lerp(0.90, 0.96, _smoothstep(local_progress))
        else:
            jump_progress = 1.0
            world = {
                "x_ratio": _lerp(0.31, 0.27, _smoothstep(local_progress)),
                "y_ratio": 0.014 * math.sin(math.pi * local_progress),
                "shadow_scale": _lerp(0.96, 1.0, _smoothstep(local_progress)),
                "shadow_opacity": _lerp(0.18, 0.24, _smoothstep(local_progress)),
            }
            scale_x = _lerp(0.96, 0.95, _smoothstep(local_progress))
            scale_y = _lerp(0.94, 0.96, _smoothstep(local_progress))
        state = {
            "action_name": "jump",
            "action_progress": jump_progress,
            "pose_index": _jump_pose(
                shot_id,
                frame_count,
                local_progress,
            ),
            "x_ratio": world["x_ratio"],
            "y_ratio": world["y_ratio"],
            "scale_x": scale_x,
            "scale_y": scale_y,
            "shadow_scale": world["shadow_scale"],
            "shadow_opacity": world["shadow_opacity"],
        }
    else:
        frame_count = counts.get("magic", _DEFAULT_FRAME_COUNTS["magic"])
        if shot_id == "charge":
            magic_progress = _lerp(0.05, 0.22, local_progress)
            x_ratio = 0.27
            y_ratio = -0.006 * math.sin(math.pi * local_progress)
            scale_x = 1.0
            scale_y = _lerp(0.99, 1.02, _smoothstep(local_progress))
        elif shot_id == "release":
            magic_progress = _lerp(0.22, 0.75, local_progress)
            x_ratio = 0.27
            y_ratio = -0.01 * math.sin(math.pi * local_progress)
            scale_x = _lerp(0.98, 1.0, _smoothstep(local_progress))
            scale_y = _lerp(1.02, 1.0, _smoothstep(local_progress))
        else:
            magic_progress = _lerp(0.75, 1.0, local_progress)
            x_ratio = _lerp(0.27, 0.25, _smoothstep(local_progress))
            y_ratio = 0.0
            scale_x = 1.0
            scale_y = 1.0
        state = {
            "action_name": "magic",
            "action_progress": magic_progress,
            "pose_index": _magic_pose(shot_id, frame_count, local_progress),
            "x_ratio": x_ratio,
            "y_ratio": y_ratio,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "shadow_scale": 0.96,
            "shadow_opacity": 0.22,
        }

    state["cut_strength"] = cut_strength
    state["shot_id"] = shot_id
    state["phase"] = phase
    state["local_progress"] = local_progress
    state.update(_camera_state(shot_id, local_progress))
    state.update(_motion_trail_state(shot_id, local_progress))
    state["foreground_strength"] = (
        0.72 if shot_id in {"approach", "flight", "apex", "resolution"} else 0.42
    )
    return state


def apply_cinematic_camera(
    frame,
    state: Mapping[str, Any],
    Image,
    ImageEnhance,
):
    """Crop the fully composited scene with a shot-specific virtual camera."""

    original_mode = getattr(frame, "mode", "RGB")
    base = frame.convert("RGB")
    width, height = base.size
    zoom = max(1.0, float(state.get("camera_zoom", 1.0) or 1.0))
    crop_width = max(2, min(width, round(width / zoom)))
    crop_height = max(2, min(height, round(height / zoom)))
    center_x = (
        float(state.get("camera_center_x", 0.5) or 0.5)
        + float(state.get("camera_shake_x", 0.0) or 0.0)
    )
    center_y = (
        float(state.get("camera_center_y", 0.5) or 0.5)
        + float(state.get("camera_shake_y", 0.0) or 0.0)
    )
    left = round(center_x * width - crop_width / 2)
    top = round(center_y * height - crop_height / 2)
    left = max(0, min(width - crop_width, left))
    top = max(0, min(height - crop_height, top))
    camera_frame = base.crop(
        (left, top, left + crop_width, top + crop_height)
    ).resize(
        (width, height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )

    phase = _clamp(float(state.get("phase", 0.5) or 0.0))
    fade = min(1.0, phase * 7.0, (1.0 - phase) * 7.0)
    camera_frame = ImageEnhance.Brightness(camera_frame).enhance(0.95 + 0.05 * fade)
    camera_frame = ImageEnhance.Contrast(camera_frame).enhance(1.035)
    if str(state.get("shot_id") or "") == "resolution":
        camera_frame = ImageEnhance.Color(camera_frame).enhance(1.04)
    return (
        camera_frame.convert("RGBA")
        if original_mode == "RGBA"
        else camera_frame.convert(original_mode)
    )


def _rotated_point(
    point: Tuple[float, float],
    center: Tuple[float, float],
    angle: float,
) -> Tuple[int, int]:
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    x, y = point
    center_x, center_y = center
    return (
        round(center_x + x * cos_angle - y * sin_angle),
        round(center_y + x * sin_angle + y * cos_angle),
    )


def apply_cinematic_foreground(
    frame,
    state: Mapping[str, Any],
    Image,
    ImageDraw,
    ImageFilter,
):
    """Add subtle edge foliage that moves faster than the background."""

    strength = _clamp(float(state.get("foreground_strength", 0.0) or 0.0))
    if strength <= 0.0 or ImageDraw is None or ImageFilter is None:
        return frame

    original_mode = getattr(frame, "mode", "RGB")
    base = frame.convert("RGBA")
    width, height = base.size
    phase = _clamp(float(state.get("phase", 0.0) or 0.0))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    leaves = (
        (-0.01, 0.18, 0.030, -0.70, (24, 71, 65)),
        (0.04, 0.83, 0.024, 0.45, (41, 92, 75)),
        (0.96, 0.12, 0.026, 0.82, (65, 74, 111)),
        (1.01, 0.69, 0.034, -0.55, (33, 78, 69)),
        (0.88, 0.94, 0.020, 0.15, (91, 63, 104)),
    )
    drift_x = (phase - 0.5) * width * 0.065
    drift_y = math.sin(phase * math.tau) * height * 0.015
    for index, (x_ratio, y_ratio, size_ratio, angle, color) in enumerate(leaves):
        center = (
            x_ratio * width - drift_x * (1.0 + index * 0.08),
            y_ratio * height + drift_y * (0.5 + index * 0.1),
        )
        size = max(5.0, min(width, height) * size_ratio)
        points = [
            _rotated_point((0.0, -size), center, angle),
            _rotated_point((size * 0.46, 0.0), center, angle),
            _rotated_point((0.0, size), center, angle),
            _rotated_point((-size * 0.46, 0.0), center, angle),
        ]
        alpha = round((42 + index * 3) * strength)
        draw.polygon(points, fill=(*color, alpha))
        draw.line(
            (
                _rotated_point((0.0, -size * 0.72), center, angle),
                _rotated_point((0.0, size * 0.72), center, angle),
            ),
            fill=(177, 203, 174, round(24 * strength)),
            width=max(1, round(size * 0.06)),
        )

    overlay = overlay.filter(
        ImageFilter.GaussianBlur(max(0.6, min(width, height) * 0.002))
    )
    composed = Image.alpha_composite(base, overlay)
    return composed if original_mode == "RGBA" else composed.convert(original_mode)


def apply_cinematic_cut_effect(
    frame,
    state: Mapping[str, Any],
    Image,
    ImageDraw,
    ImageFilter,
):
    """Apply a light flash or edge speed lines without covering the character."""

    strength = _clamp(float(state.get("cut_strength", 0.0) or 0.0))
    if strength <= 0.0:
        return frame

    original_mode = getattr(frame, "mode", "RGBA")
    base = frame.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size

    flash_alpha = round(90 * strength)
    edge_alpha = round(120 * strength)
    top_band = max(8, round(height * 0.08))
    side_band = max(10, round(width * 0.09))
    draw.rectangle((0, 0, width, top_band), fill=(255, 255, 255, flash_alpha))
    draw.rectangle((0, 0, side_band, height), fill=(180, 225, 255, edge_alpha))
    draw.rectangle((width - side_band, 0, width, height), fill=(180, 225, 255, edge_alpha))

    line_count = 4
    line_alpha = round(80 * strength)
    left_stop = round(width * 0.28)
    right_start = round(width * 0.72)
    for index in range(line_count):
        y = round(height * (0.18 + index * 0.11))
        draw.line(
            ((0, y), (left_stop, max(0, y - round(height * 0.04)))),
            fill=(210, 235, 255, line_alpha),
            width=max(1, round(height * 0.008)),
        )
        draw.line(
            ((width, y), (right_start, max(0, y - round(height * 0.04)))),
            fill=(210, 235, 255, line_alpha),
            width=max(1, round(height * 0.008)),
        )

    blurred = overlay.filter(ImageFilter.GaussianBlur(max(2, round(height * 0.01))))
    composed = Image.alpha_composite(base, blurred)
    return composed if original_mode == "RGBA" else composed.convert(original_mode)


__all__ = [
    "ANIMATION_MODE",
    "apply_cinematic_camera",
    "apply_cinematic_cut_effect",
    "apply_cinematic_foreground",
    "resolve_cinematic_shot",
    "supports_cinematic_animatic",
]
