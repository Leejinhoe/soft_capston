from typing import Any, Dict, Optional


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
        "walk",
        (
            "walk",
            "walking",
            "stroll",
            "journey",
            "run",
            "running",
            "sprint",
            "dash",
            "\uac77",
            "\uac78\uc5b4",
            "\uc0b0\ucc45",
            "\uc5ec\ud589",
            "\ub2ec\ub9ac",
            "\ub6f0",
        ),
    ),
)


def detect_character_action_group(
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    normalized_story = " ".join(story_text.lower().split())
    context_actions = {
        str(action).strip().lower().replace("-", "_")
        for action in (visual_context or {}).get("action_tags", [])
        if str(action).strip()
    }
    if context_actions.intersection(
        {"fight", "fighting", "battle", "combat", "attack", "defending"}
    ):
        return "fight"
    if context_actions.intersection(
        {"walk", "walking", "run", "running", "journey", "travel"}
    ):
        return "walk"
    for action_group, keywords in ACTION_GROUP_KEYWORDS:
        if any(keyword in normalized_story for keyword in keywords):
            return action_group
    return None


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
    if not profile:
        return None
    action_group = detect_character_action_group(story_text, visual_context)
    if not action_group:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return None
    return next(
        (
            asset
            for asset in assets
            if asset.get("quality_tier") == "premium_action_cycle"
            and asset.get("animation_group") == action_group
            and asset.get("image_file_id")
        ),
        None,
    )


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
