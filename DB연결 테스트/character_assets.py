from typing import Any, Dict, Optional


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
