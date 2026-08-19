from typing import Any, Dict, Optional


MOTION_SHEET_QUALITY_TIER = "video_motion_sheet_v3"
TARGET_JOURNEY_SHEET_QUALITY_TIER = "video_target_journey_sheet_v4"
RUN_CYCLE_SHEET_QUALITY_TIER = "video_run_cycle_v16"
JUMP_CYCLE_SHEET_QUALITY_TIER = "video_jump_cycle_v28"
ACTION_SHEET_QUALITY_TIER = "video_action_sheet_v28"
ACTION_CYCLE_QUALITY_TIERS = {
    "battle": "video_battle_cycle_v28",
    "magic": "video_magic_cycle_v22",
    "interaction": "video_interaction_cycle_v28",
    "sit": "video_sit_cycle_v1",
    "stand": "video_stand_cycle_v1",
}

# Keep already-seeded GridFS assets usable while the catalog is reseeded with
# v28. Selection always prefers the canonical tier above, then the newest
# known legacy tier.
LEGACY_JUMP_CYCLE_QUALITY_TIERS = (
    "video_jump_cycle_v23",
    "video_jump_cycle_v20",
)
LEGACY_ACTION_SHEET_QUALITY_TIERS = (
    "video_action_sheet_v23",
    "video_action_sheet_v21",
)
LEGACY_ACTION_CYCLE_QUALITY_TIERS = {
    "battle": (
        "video_battle_cycle_v23",
        "video_battle_cycle_v22",
    ),
    "interaction": (
        "video_interaction_cycle_v23",
        "video_interaction_cycle_v22",
    ),
}

VIDEO_ASSET_QUALITY_TIERS = {
    MOTION_SHEET_QUALITY_TIER,
    TARGET_JOURNEY_SHEET_QUALITY_TIER,
    RUN_CYCLE_SHEET_QUALITY_TIER,
    JUMP_CYCLE_SHEET_QUALITY_TIER,
    ACTION_SHEET_QUALITY_TIER,
    *ACTION_CYCLE_QUALITY_TIERS.values(),
    *LEGACY_JUMP_CYCLE_QUALITY_TIERS,
    *LEGACY_ACTION_SHEET_QUALITY_TIERS,
    *{
        tier
        for tiers in LEGACY_ACTION_CYCLE_QUALITY_TIERS.values()
        for tier in tiers
    },
}


def _select_video_asset(
    assets: list[Dict[str, Any]],
    quality_tiers: tuple[str, ...],
    pose: str,
) -> Optional[Dict[str, Any]]:
    """Select the newest compatible asset before falling back by pose."""

    for quality_tier in quality_tiers:
        match = next(
            (asset for asset in assets if asset.get("quality_tier") == quality_tier),
            None,
        )
        if match:
            return match
    return next((asset for asset in assets if asset.get("pose") == pose), None)


def select_character_asset(
    profile: Optional[Dict[str, Any]],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
    preferred_pose: Optional[str] = None,
    preferred_emotion: Optional[str] = None,
    prefer_premium_reference: bool = False,
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list) or not assets:
        return None

    scene_assets = [
        asset
        for asset in assets
        if asset.get("quality_tier") not in VIDEO_ASSET_QUALITY_TIERS
        and asset.get("pose")
        not in {
            "motion-sheet", "target-journey-sheet", "run-cycle-sheet",
            "jump-cycle-sheet",
            "action-sheet",
            "battle-cycle-sheet", "magic-cycle-sheet", "interaction-cycle-sheet",
            "sit-cycle-sheet", "stand-cycle-sheet",
        }
    ]
    if not scene_assets:
        return None

    normalized_story = " ".join(story_text.lower().split())
    default_asset = next(
        (asset for asset in scene_assets if asset.get("pose") == "default"),
        scene_assets[0],
    )
    normalized_preferred_pose = str(preferred_pose or "").strip().lower()
    normalized_preferred_emotion = str(preferred_emotion or "").strip().lower()
    explicit_emotions = {
        str(item).strip().lower()
        for item in (visual_context or {}).get("emotion_tags", [])
        if str(item).strip()
    }
    best_asset = default_asset
    best_score = 0
    for asset in scene_assets:
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
        if str(asset.get("emotion") or "").strip().lower() in explicit_emotions:
            score += 16
        if normalized_preferred_pose and str(asset.get("pose") or "").strip().lower() == normalized_preferred_pose:
            score += 12
        if (
            normalized_preferred_emotion
            and not explicit_emotions
            and str(asset.get("emotion") or "").strip().lower()
            == normalized_preferred_emotion
        ):
            score += 8
        if (
            prefer_premium_reference
            and asset.get("quality_tier") == "premium_reference"
        ):
            score += 100
        if score > best_score:
            best_asset = asset
            best_score = score

    return best_asset


def select_character_motion_sheet(
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
            if asset.get("quality_tier") == MOTION_SHEET_QUALITY_TIER
            or asset.get("pose") == "motion-sheet"
        ),
        None,
    )


def select_character_target_journey_sheet(
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
            if asset.get("quality_tier") == TARGET_JOURNEY_SHEET_QUALITY_TIER
            or asset.get("pose") == "target-journey-sheet"
        ),
        None,
    )


def select_character_run_cycle_sheet(
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
            if asset.get("quality_tier") == RUN_CYCLE_SHEET_QUALITY_TIER
            or asset.get("pose") == "run-cycle-sheet"
        ),
        None,
    )


def select_character_jump_cycle_sheet(
    profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return None
    return _select_video_asset(
        assets,
        (JUMP_CYCLE_SHEET_QUALITY_TIER, *LEGACY_JUMP_CYCLE_QUALITY_TIERS),
        "jump-cycle-sheet",
    )


def select_character_action_sheet(
    profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return None
    return _select_video_asset(
        assets,
        (ACTION_SHEET_QUALITY_TIER, *LEGACY_ACTION_SHEET_QUALITY_TIERS),
        "action-sheet",
    )


def select_character_action_cycle_sheet(
    profile: Optional[Dict[str, Any]],
    action: str,
) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    assets = profile.get("assets")
    if not isinstance(assets, list):
        return None
    normalized_action = "interaction" if action == "rescue" else str(action or "")
    canonical_quality_tier = ACTION_CYCLE_QUALITY_TIERS.get(normalized_action)
    if not canonical_quality_tier:
        return None
    return _select_video_asset(
        assets,
        (
            canonical_quality_tier,
            *LEGACY_ACTION_CYCLE_QUALITY_TIERS.get(normalized_action, set()),
        ),
        f"{normalized_action}-cycle-sheet",
    )


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
    parts.extend(
        f"clearly visible {str(item).replace('_', ' ')}"
        for item in context.get("prop_tags", [])
    )
    parts.extend(
        f"{str(item).replace('_', ' ')} motion"
        for item in context.get("motion_modifier_tags", [])
    )
    parts.extend(
        f"{str(item).replace('_', ' ')} expression"
        for item in context.get("emotion_tags", [])
    )
    semantics = context.get("action_semantics") or {}
    interaction_kind = str(semantics.get("interaction_kind") or "").strip()
    if interaction_kind:
        parts.append(interaction_kind.replace("_", " "))
    if semantics.get("requires_partner"):
        subject_role = str(semantics.get("subject_role") or "character").replace(
            "_", " "
        )
        partner_role = str(semantics.get("partner_role") or "partner").replace(
            "_", " "
        )
        parts.append(f"{subject_role} visibly interacting with {partner_role}")
    if semantics.get("requires_object") and semantics.get("object_role"):
        object_role = str(semantics["object_role"]).replace("_", " ")
        parts.append(f"clearly visible {object_role}")
    if semantics.get("body_focus"):
        body_focus = str(semantics["body_focus"]).replace("_", " ")
        parts.append(f"readable {body_focus} action")
    return ", ".join(parts) or None
