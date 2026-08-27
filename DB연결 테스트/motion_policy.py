"""Shared policy for single-character motion classification and training."""

from __future__ import annotations

from typing import Any, Mapping


# Keep this list conservative: every motion must be readable without a partner
# or a handoff/object interaction in the training example.
SOLO_ANIMATION_ACTIONS = frozenset(
    {"journey", "jump", "magic", "investigate", "wave", "sit", "stand"}
)

# Every local clip is authored as a short, readable arc.  The names are kept
# stable because they are also useful to dataset and renderer diagnostics.
SOLO_MOTION_PHASES = ("prepare", "act", "recover")

SOLO_TRAINING_POSES = (
    "default",
    "happy",
    "sad",
    "angry",
    "walking",
    "magic",
)

PARTNER_ANIMATION_ACTIONS = frozenset({"battle", "conversation", "rescue"})


def validate_motion_semantics(semantics: Mapping[str, Any] | None) -> list[str]:
    """Return deterministic errors for the action's participant/object contract."""
    if not semantics:
        return ["missing_semantics"]
    action = str(semantics.get("animation_action") or "").strip().lower()
    participants = semantics.get("participants") or []
    keys = semantics.get("character_keys") or [
        item.get("character_key") for item in participants if isinstance(item, Mapping)
    ]
    count = semantics.get("participant_count", len(keys) or 1)
    errors = []
    try:
        count = int(count)
    except (TypeError, ValueError):
        errors.append("invalid_participant_count")
        count = 0
    if count != len(set(key for key in keys if key)) and participants:
        errors.append("participant_count_mismatch")
    if any(not key for key in keys) and participants:
        errors.append("participant_missing_character_key")
    if action in PARTNER_ANIMATION_ACTIONS and count < 2:
        errors.append("action_requires_partner")
    if semantics.get("requires_partner") and count < 2:
        errors.append("partner_required")
    if semantics.get("requires_object") and not (semantics.get("target") or semantics.get("target_type")):
        errors.append("object_target_missing")
    if action == "journey" and not (semantics.get("directionality") or semantics.get("direction")):
        errors.append("journey_missing_direction")
    return list(dict.fromkeys(errors))


def is_solo_action_semantics(semantics: Mapping[str, Any] | None) -> bool:
    """Return whether a semantic action is safe for single-character training."""

    if not semantics:
        return False
    action = str(semantics.get("animation_action") or "").strip().lower()
    if action not in SOLO_ANIMATION_ACTIONS:
        return False
    try:
        participant_count = int(semantics.get("participant_count", 1))
    except (TypeError, ValueError):
        return False
    return (
        participant_count == 1
        and not bool(semantics.get("requires_partner"))
        and not bool(semantics.get("requires_object"))
        and str(semantics.get("motion_mode") or "") != "environmental"
        and not any(
            error in validate_motion_semantics(semantics)
            for error in (
                "action_requires_partner",
                "partner_required",
                "participant_count_mismatch",
                "journey_missing_direction",
            )
        )
    )
