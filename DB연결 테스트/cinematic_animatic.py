"""Pure timeline helpers for an intentional storybook cinematic animatic.

This module does not interpolate character poses. Each shot chooses a fixed
pose index while root motion, jump height, and simple cut effects remain
continuous over time.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional


ANIMATION_MODE = "cinematic_storyboard"

_DEFAULT_FRAME_COUNTS = {
    "walk": 2,
    "run": 6,
    "jump": 6,
    "magic": 6,
}

_SHOT_LAYOUT = (
    ("approach", 0.00, 0.27, "approach"),
    ("notice", 0.27, 0.34, "approach"),
    ("crouch", 0.34, 0.41, "jump"),
    ("takeoff", 0.41, 0.49, "jump"),
    ("flight", 0.49, 0.57, "jump"),
    ("apex", 0.57, 0.64, "jump"),
    ("landing", 0.64, 0.72, "jump"),
    ("recovery", 0.72, 0.79, "jump"),
    ("charge", 0.79, 0.89, "magic"),
    ("release", 0.89, 0.96, "magic"),
    ("resolution", 0.96, 1.00, "magic"),
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


def _cut_strength(
    *,
    frame_index: int,
    total_frames: int,
    frame_rate: float,
    shot_start: float,
) -> float:
    if shot_start <= 0.0 or total_frames <= 1:
        return 0.0
    start_frame = max(1, round(shot_start * (total_frames - 1)))
    window = max(2, round(max(frame_rate, 1.0) * 0.08))
    offset = frame_index - start_frame
    if offset < 0 or offset >= window:
        return 0.0
    return _clamp(1.0 - (offset / max(window - 1, 1)))


def _approach_pose(
    action_name: str,
    local_progress: float,
    frame_count: int,
) -> int:
    if frame_count <= 1:
        return 0
    step_count = 5 if action_name == "run" else 4
    step_index = min(
        step_count - 1,
        int(_clamp(local_progress) * step_count),
    )
    return step_index % frame_count


def _stepped_approach_progress(
    local_progress: float,
    action_name: str,
) -> float:
    step_count = 5 if action_name == "run" else 4
    progress = _clamp(local_progress)
    if progress >= 1.0:
        return 1.0
    step_position = progress * step_count
    step_index = min(step_count - 1, int(step_position))
    within_step = step_position - step_index
    swing_progress = _smoothstep(min(1.0, within_step / 0.42))
    return (step_index + swing_progress) / step_count


def _jump_pose(shot_id: str, frame_count: int) -> int:
    if shot_id == "crouch":
        return _pose_index(frame_count, 1)
    if shot_id == "takeoff":
        return _pose_index(frame_count, 2)
    if shot_id == "flight":
        return _pose_index(frame_count, 2)
    if shot_id == "apex":
        return _pose_index(frame_count, 3)
    if shot_id == "landing":
        return _pose_index(frame_count, 4)
    return _pose_index(frame_count, 5)


def _magic_pose(shot_id: str, frame_count: int, local_progress: float) -> int:
    if shot_id == "charge":
        return _pose_index(frame_count, 1 if local_progress < 0.5 else 2)
    if shot_id == "release":
        return _pose_index(frame_count, 3 if local_progress < 0.5 else 4)
    return _pose_index(frame_count, frame_count - 1)


def _jump_world_state(jump_progress: float) -> Dict[str, float]:
    travel = _smoothstep(jump_progress)
    lift = math.sin(math.pi * _clamp(jump_progress))
    return {
        "x_ratio": _lerp(-0.06, 0.25, travel),
        "y_ratio": -0.22 * lift,
        "shadow_scale": _lerp(1.0, 0.72, lift),
        "shadow_opacity": _lerp(0.25, 0.11, lift),
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
    safe_frame_rate = max(1.0, float(frame_rate or 1.0))
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
    cut_strength = _cut_strength(
        frame_index=safe_frame_index,
        total_frames=safe_total_frames,
        frame_rate=safe_frame_rate,
        shot_start=float(shot["start"]),
    )
    if shot_id not in {"takeoff", "landing", "release"}:
        cut_strength = 0.0
    else:
        cut_strength *= 0.55

    if shot["action_group"] == "approach":
        frame_count = counts.get(approach_action, counts["walk"])
        walk_wave = math.sin(math.tau * local_progress * (3.0 if approach_action == "run" else 2.0))
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
                    -0.24,
                    -0.08,
                    _stepped_approach_progress(
                        local_progress,
                        approach_action,
                    ),
                )
                if shot_id == "approach"
                else -0.08
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
                "x_ratio": _lerp(-0.06, -0.05, _smoothstep(local_progress)),
                "y_ratio": 0.018 * _smoothstep(local_progress),
                "shadow_scale": 1.03,
                "shadow_opacity": 0.28,
            }
            scale_x = _lerp(1.0, 1.04, _smoothstep(local_progress))
            scale_y = _lerp(1.0, 0.94, _smoothstep(local_progress))
        elif shot_id == "takeoff":
            jump_progress = _lerp(0.14, 0.32, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(1.03, 0.98, _smoothstep(local_progress))
            scale_y = _lerp(0.96, 1.04, _smoothstep(local_progress))
        elif shot_id == "flight":
            jump_progress = _lerp(0.32, 0.50, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(0.98, 0.96, _smoothstep(local_progress))
            scale_y = _lerp(1.04, 1.01, _smoothstep(local_progress))
        elif shot_id == "apex":
            jump_progress = _lerp(0.50, 0.72, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = 0.99
            scale_y = 1.01
        elif shot_id == "landing":
            jump_progress = _lerp(0.74, 1.0, local_progress)
            world = _jump_world_state(jump_progress)
            scale_x = _lerp(1.04, 1.0, _smoothstep(local_progress))
            scale_y = _lerp(0.95, 1.0, _smoothstep(local_progress))
        else:
            jump_progress = 1.0
            world = {
                "x_ratio": _lerp(0.20, 0.15, _smoothstep(local_progress)),
                "y_ratio": 0.014 * math.sin(math.pi * local_progress),
                "shadow_scale": _lerp(0.96, 1.0, _smoothstep(local_progress)),
                "shadow_opacity": _lerp(0.18, 0.24, _smoothstep(local_progress)),
            }
            scale_x = _lerp(1.02, 1.0, _smoothstep(local_progress))
            scale_y = _lerp(0.98, 1.0, _smoothstep(local_progress))
        state = {
            "action_name": "jump",
            "action_progress": jump_progress,
            "pose_index": _jump_pose(shot_id, frame_count),
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
            x_ratio = 0.18
            y_ratio = -0.006 * math.sin(math.pi * local_progress)
            scale_x = 1.0
            scale_y = _lerp(0.99, 1.02, _smoothstep(local_progress))
        elif shot_id == "release":
            magic_progress = _lerp(0.28, 0.72, local_progress)
            x_ratio = 0.18
            y_ratio = -0.01 * math.sin(math.pi * local_progress)
            scale_x = _lerp(0.98, 1.0, _smoothstep(local_progress))
            scale_y = _lerp(1.02, 1.0, _smoothstep(local_progress))
        else:
            magic_progress = _lerp(0.72, 1.0, local_progress)
            x_ratio = _lerp(0.18, 0.20, _smoothstep(local_progress))
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
    return state


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
    "apply_cinematic_cut_effect",
    "resolve_cinematic_shot",
    "supports_cinematic_animatic",
]
