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
    )
