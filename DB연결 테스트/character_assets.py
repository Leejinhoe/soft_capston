import re
from typing import Any, Dict, List, Optional


POSE_ACTION_KEYWORDS = {
    "walking": (
        "walk",
        "walking",
        "run",
        "runs",
        "running",
        "race",
        "sprint",
        "dash",
        "\uac77",
        "\uac78\uc5b4",
        "\ub2ec\ub9ac",
        "\ub6f0",
    ),
    "talking": (
        "talk",
        "speak",
        "whisper",
        "sing",
        "\ub9d0\ud558",
        "\uc774\uc57c\uae30",
        "\ub178\ub798",
    ),
    "casting-magic": (
        "cast",
        "spell",
        "magic",
        "\ub9c8\ubc95",
        "\uc8fc\ubb38",
    ),
    "rescuing": (
        "help",
        "rescue",
        "protect",
        "\uad6c\ud558",
        "\uad6c\ucd9c",
        "\uc9c0\ucf1c",
    ),
}

ACTION_GROUP_KEYWORDS = (
    (
        "fight",
        (
            "fight",
            "fighting",
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
            "\uac80\uc73c\ub85c",
            "\uce7c\uc744",
            "\ubca0\uc5b4",
            "\ub9c9\uc544",
            "\ubc29\uc5b4",
        ),
    ),
    (
        "run",
        (
            "run",
            "runs",
            "running",
            "sprint",
            "dash",
            "\ub2ec\ub9ac",
            "\ub6f0",
        ),
    ),
    (
        "jump",
        (
            "jump",
            "jumps",
            "jumping",
            "leap",
            "hop",
            "\uc810\ud504",
            "\ub6f0\uc5b4",
            "\ub3c4\uc57d",
        ),
    ),
    (
        "magic",
        (
            "magic",
            "spell",
            "cast",
            "casts",
            "casting",
            "\ub9c8\ubc95",
            "\uc8fc\ubb38",
        ),
    ),
    (
        "walk",
        (
            "walk",
            "walks",
            "walking",
            "stroll",
            "journey",
            "\uac77",
            "\uac78\uc5b4",
            "\uc0b0\ucc45",
            "\uc5ec\ud589",
        ),
    ),
)

ACTION_CONTEXT_ALIASES = {
    "fight": {"fight", "fighting", "battle", "combat", "attack", "defending"},
    "run": {"run", "running", "sprint", "dash"},
    "jump": {"jump", "jumping", "leap", "hop"},
    "magic": {"magic", "spell", "casting_magic", "cast"},
    "walk": {"walk", "walking", "journey", "travel"},
}


def detect_character_action_groups(
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    normalized_story = " ".join(story_text.lower().split())
    matches = []
    for action_group, keywords in ACTION_GROUP_KEYWORDS:
        positions = []
        for keyword in keywords:
            if not keyword:
                continue
            if keyword.isascii():
                match = re.search(
                    rf"\b{re.escape(keyword)}\b",
                    normalized_story,
                )
                position = match.start() if match else -1
            else:
                position = normalized_story.find(keyword)
            if position >= 0:
                positions.append(position)
        if positions:
            matches.append((min(positions), action_group))

    context_actions = {
        str(action).strip().lower().replace("-", "_")
        for action in (visual_context or {}).get("action_tags", [])
        if str(action).strip()
    }
    context_position = len(normalized_story) + 1
    for action_group, aliases in ACTION_CONTEXT_ALIASES.items():
        if context_actions.intersection(aliases):
            matches.append((context_position, action_group))
            context_position += 1

    ordered_groups = []
    for _, action_group in sorted(matches, key=lambda item: item[0]):
        if action_group not in ordered_groups:
            ordered_groups.append(action_group)
    return ordered_groups


def detect_character_action_group(
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    action_groups = detect_character_action_groups(story_text, visual_context)
    return action_groups[0] if action_groups else None


def select_premium_reference_asset(
    profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return None
    return next(
        (
            asset
            for asset in assets
            if asset.get("quality_tier") == "premium_reference"
            and asset.get("image_file_id")
        ),
        None,
    )


def select_character_action_cycle(
    profile: Optional[Dict[str, Any]],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    action_cycles = select_character_action_cycles(
        profile,
        story_text,
        visual_context,
    )
    return action_cycles[0] if action_cycles else None


def select_character_action_cycles(
    profile: Optional[Dict[str, Any]],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not profile:
        return []
    action_groups = detect_character_action_groups(story_text, visual_context)
    if not action_groups:
        return []
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return []

    selected = []
    for action_group in action_groups:
        candidates = [
            asset
            for asset in assets
            if asset.get("quality_tier") == "premium_action_cycle"
            and asset.get("animation_group") == action_group
            and asset.get("image_file_id")
        ]
        if candidates:
            selected.append(
                max(
                    candidates,
                    key=lambda asset: (
                        int(asset.get("animation_version") or 1),
                        int(asset.get("animation_frame_count") or 0),
                    ),
                )
            )
    return selected


def select_character_asset(
    profile: Optional[Dict[str, Any]],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list) or not assets:
        return None

    normalized_story = " ".join(story_text.lower().split())
    default_asset = next(
        (asset for asset in assets if asset.get("pose") == "default"),
        assets[0],
    )
    best_asset = default_asset
    best_score = 0
    for asset in assets:
        keywords = asset.get("scene_keywords") or []
        score = sum(
            1
            for keyword in keywords
            if isinstance(keyword, str)
            and keyword.strip()
            and keyword.strip().lower() in normalized_story
        )
        pose = str(asset.get("pose") or "").strip().lower()
        action_matches = sum(
            1
            for keyword in POSE_ACTION_KEYWORDS.get(pose, ())
            if keyword in normalized_story
        )
        score += action_matches * 4
        context = visual_context or {}
        if asset.get("pose") in context.get("action_tags", []):
            score += 5
        if asset.get("emotion") in context.get("emotion_tags", []):
            score += 3
        if score > best_score:
            best_asset = asset
            best_score = score

    return best_asset


def build_character_action_hint(
    asset: Optional[Dict[str, Any]],
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    parts = []
    if asset:
        pose = str(asset.get("pose") or "default").strip()
        emotion = str(asset.get("emotion") or "neutral").strip()
        parts.append(f"{pose} pose, {emotion} expression")
    context = visual_context or {}
    parts.extend(str(item).replace("_", " ") for item in context.get("effect_tags", []))
    return ", ".join(parts) or None
