"""Small, deterministic contracts shared by story scenes and media jobs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional


SUPPORTED_SCENE_ACTIONS = frozenset(
    {
        "battle",
        "conversation",
        "idle",
        "interaction",
        "investigate",
        "journey",
        "jump",
        "magic",
        "rescue",
        "sit",
        "stand",
        "wave",
    }
)

_ACTION_ALIASES = {
    "walk": "journey",
    "walking": "journey",
    "run": "journey",
    "running": "journey",
    "travel": "journey",
    "move": "journey",
    "approach": "journey",
    "걸어": "journey",
    "걷기": "journey",
    "달리기": "journey",
    "이동": "journey",
    "look": "investigate",
    "search": "investigate",
    "find": "investigate",
    "inspect": "investigate",
    "explore": "investigate",
    "찾기": "investigate",
    "살펴보기": "investigate",
    "탐색": "investigate",
    "open": "interaction",
    "close": "interaction",
    "take": "interaction",
    "hold": "interaction",
    "push": "interaction",
    "pull": "interaction",
    "열기": "interaction",
    "잡기": "interaction",
    "말하기": "conversation",
    "talk": "conversation",
    "speak": "conversation",
    "greet": "wave",
    "인사": "wave",
    "sit down": "sit",
    "앉기": "sit",
    "stand up": "stand",
    "일어서기": "stand",
}

_DIRECTION_ALIASES = {
    "toward target": "toward_target",
    "towards target": "toward_target",
    "target": "toward_target",
    "toward route": "toward_route",
    "route": "toward_route",
    "left to right": "left_to_right",
    "right to left": "right_to_left",
    "앞으로": "forward",
    "왼쪽에서 오른쪽": "left_to_right",
    "오른쪽에서 왼쪽": "right_to_left",
    "정지": "stationary",
    "stationary": "stationary",
    "forward": "forward",
    "backward": "backward",
}


def _normalize_text(value: Any, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _normalize_token(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _normalize_action(value: Any) -> Optional[str]:
    token = _normalize_token(value)
    if not token:
        return None
    action = _ACTION_ALIASES.get(token, token)
    return action.replace(" ", "_") if action in SUPPORTED_SCENE_ACTIONS else action


def _normalize_direction(value: Any) -> Optional[str]:
    token = _normalize_token(value)
    if not token:
        return None
    return _DIRECTION_ALIASES.get(token, token.replace(" ", "_"))


def _normalize_list(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        return []
    normalized = []
    seen = set()
    for value in values:
        token = _normalize_text(value, limit=80).lower().replace(" ", "_")
        if token and token not in seen:
            normalized.append(token)
            seen.add(token)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_participants(values: Any, *, limit: int) -> list[Dict[str, Any]]:
    """Normalize participant declarations without inferring identity from names."""
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        return []
    participants = []
    seen = set()
    for value in values:
        if isinstance(value, Mapping):
            key = _normalize_text(
                value.get("character_key") or value.get("characterKey") or value.get("key"),
                limit=64,
            )
            role = _normalize_token(value.get("role") or value.get("participant_role")) or None
            item = {"character_key": key or None, "role": role}
        else:
            key = _normalize_text(value, limit=64)
            item = {"character_key": key or None, "role": None}
        identity = item["character_key"]
        if identity and identity not in seen:
            participants.append(item)
            seen.add(identity)
        if len(participants) >= limit:
            break
    return participants


def validate_scene_contract(contract: Mapping[str, Any]) -> list[str]:
    """Check that selected characters, roles, action, target, and direction agree."""
    errors = list(contract.get("validation_errors") or [])
    participants = contract.get("participants") or []
    keys = [p.get("character_key") for p in participants if isinstance(p, Mapping)]
    selected = contract.get("character_key")
    count = contract.get("participant_count")
    if count is not None and participants and count != len(participants):
        errors.append("participant_count_mismatch")
    if selected and participants and selected not in keys:
        errors.append("selected_character_not_participant")
    if participants and any(not p.get("character_key") for p in participants if isinstance(p, Mapping)):
        errors.append("participant_missing_character_key")
    if contract.get("requires_partner") and participants and len(participants) < 2:
        errors.append("partner_required")
    has_participant_declaration = bool(participants) or count is not None
    if (
        contract.get("action") in {"conversation", "battle", "rescue"}
        and has_participant_declaration
        and len(participants) < 2
    ):
        errors.append("action_requires_partner")
    if contract.get("action") == "interaction" and not contract.get("requires_partner") and not (
        contract.get("target") or contract.get("requires_object")
    ):
        errors.append("interaction_missing_target")
    return list(dict.fromkeys(errors))


def normalize_scene_contract(
    raw: Optional[Mapping[str, Any]],
    *,
    character_key: Optional[str] = None,
    source: str = "explicit",
) -> Dict[str, Any]:
    """Normalize a caller-provided contract without guessing unsupported actions."""

    payload = dict(raw or {})
    raw_action = payload.get("action") or payload.get("animation_action")
    action = _normalize_action(raw_action)
    errors = []
    if raw_action and action not in SUPPORTED_SCENE_ACTIONS:
        errors.append(f"unsupported_action:{_normalize_token(raw_action)}")

    direction = _normalize_direction(
        payload.get("background_direction") or payload.get("directionality")
    )
    participants = _normalize_participants(
        payload.get("participants") or payload.get("participant_roles") or [], limit=4
    )
    character_keys = _normalize_list(payload.get("character_keys"), limit=4)
    if character_keys and not participants:
        participants = [{"character_key": key, "role": None} for key in character_keys]
    participant_count = (
        max(0, min(int(payload["participant_count"]), 4))
        if payload.get("participant_count") is not None
        else (len(participants) or None)
    )
    contract = {
        "version": 1,
        "source": source,
        "character_key": _normalize_text(character_key or payload.get("character_key"), limit=64)
        or None,
        "participants": participants,
        "character_keys": [p["character_key"] for p in participants],
        "participant_roles": {
            p["character_key"]: p["role"] for p in participants if p.get("character_key") and p.get("role")
        },
        "scene_goal": _normalize_text(payload.get("scene_goal"), limit=180) or None,
        "action": action if action in SUPPORTED_SCENE_ACTIONS else None,
        "target": _normalize_text(payload.get("target"), limit=100) or None,
        "required_props": _normalize_list(payload.get("required_props"), limit=8),
        "participant_count": participant_count,
        "requires_partner": (
            bool(payload["requires_partner"])
            if payload.get("requires_partner") is not None
            else None
        ),
        "requires_object": (
            bool(payload["requires_object"])
            if payload.get("requires_object") is not None
            else None
        ),
        "visual_anchor": _normalize_text(payload.get("visual_anchor"), limit=240) or None,
        "background_direction": direction,
        "dialogue": _normalize_text(payload.get("dialogue"), limit=240) or None,
        "validation_errors": errors,
    }
    contract["validation_errors"] = validate_scene_contract(contract)
    contract["valid"] = not contract["validation_errors"]
    return contract


def apply_scene_contract(
    visual_context: Optional[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> Dict[str, Any]:
    """Make explicit contract values take precedence over text keyword matches."""

    context = dict(visual_context or {})
    semantics = dict(context.get("action_semantics") or {})
    action = contract.get("action")
    if action:
        semantics["animation_action"] = action
        context["action_tags"] = [action]
    direction = contract.get("background_direction")
    if direction:
        semantics["directionality"] = direction
    target = contract.get("target")
    if target:
        semantics["target_type"] = target
    if contract.get("participant_count") is not None:
        semantics["participant_count"] = contract["participant_count"]
    if contract.get("participants"):
        semantics["participants"] = [dict(p) for p in contract["participants"]]
        semantics["character_keys"] = list(contract["character_keys"])
        semantics["participant_roles"] = dict(contract["participant_roles"])
    if contract.get("requires_partner") is not None:
        semantics["requires_partner"] = contract["requires_partner"]
    if contract.get("requires_object") is not None:
        semantics["requires_object"] = contract["requires_object"]
    if contract.get("required_props"):
        context["prop_tags"] = list(contract["required_props"])
    context["action_semantics"] = semantics
    context["scene_contract"] = dict(contract)
    return context


def resolve_scene_contract(
    *,
    story_text: str,
    visual_context: Optional[Mapping[str, Any]],
    motion_plan: Mapping[str, Any],
    character_key: Optional[str],
    explicit: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill the contract from the final motion plan while preserving explicit values."""

    contract = normalize_scene_contract(
        explicit,
        character_key=character_key,
        source="explicit" if explicit else "derived",
    )
    if explicit and not contract["valid"]:
        return contract

    semantics = dict((visual_context or {}).get("action_semantics") or {})
    contract["action"] = contract.get("action") or motion_plan.get("action") or "idle"
    contract["target"] = contract.get("target") or motion_plan.get("target") or "scene"
    contract["background_direction"] = (
        contract.get("background_direction")
        or motion_plan.get("directionality")
        or semantics.get("directionality")
        or motion_plan.get("alignment", {}).get("body_facing")
    )
    contract["required_props"] = contract.get("required_props") or list(
        (visual_context or {}).get("prop_tags") or []
    )[:8]
    contract["scene_goal"] = contract.get("scene_goal") or (
        f"{contract['action']} toward {contract['target']}"
        if contract["action"] == "journey"
        else f"perform {contract['action']}"
    )
    contract["visual_anchor"] = contract.get("visual_anchor") or " ".join(
        value
        for value in (
            str(contract["action"]),
            str(contract["target"]),
            " ".join(contract["required_props"]),
        )
        if value and value != "None"
    )[:240]
    contract["story_text_excerpt"] = _normalize_text(story_text, limit=180)
    contract["valid"] = True
    contract["validation_errors"] = validate_scene_contract(contract)
    contract["valid"] = not contract["validation_errors"]
    return contract
