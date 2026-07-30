import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional


ROLE_PRIORITY = (
    "hero",
    "target",
    "antagonist",
    "companion",
    "guide",
)

NON_CHARACTER_ROLES = {"key_item", "item", "artifact", "location", "setting"}

_QUOTED_NAME_PATTERN = re.compile(r"['\"\u2018\u2019\u201c\u201d]([^'\"\u2018\u2019\u201c\u201d]+)['\"\u2018\u2019\u201c\u201d]")

_GENDER_TERMS = {
    "female": {
        "female", "woman", "girl", "princess", "queen", "mother", "grandmother",
        "여성", "여자", "소녀", "공주", "여왕", "왕비", "어머니", "할머니",
    },
    "male": {
        "male", "man", "boy", "prince", "king", "father", "grandfather",
        "남성", "남자", "소년", "왕자", "왕", "아버지", "할아버지", "나무꾼",
    },
}

_AGE_TERMS = {
    "child": {
        "child", "kid", "boy", "girl", "young child",
        "아이", "어린이", "꼬마", "소년", "소녀",
    },
    "teen": {
        "teen", "teenage", "teenager", "adolescent",
        "십대", "청소년",
    },
    "young_adult": {
        "young adult", "young man", "young woman",
        "청년", "젊은 남성", "젊은 여성",
    },
    "adult": {
        "adult", "man", "woman", "father", "mother",
        "성인", "남성", "여성", "아버지", "어머니",
    },
    "elder": {
        "elder", "elderly", "old man", "old woman", "grandfather", "grandmother",
        "노인", "노년", "할아버지", "할머니",
    },
}

_ROLE_HINTS = {
    "hero": {"hero", "warrior", "explorer", "guardian", "mage"},
    "target": {"target", "princess", "prince", "royal", "healer"},
    "antagonist": {"antagonist", "rival", "king", "queen", "dark_fantasy"},
    "companion": {"companion", "helper", "fairy", "friendship", "guardian"},
    "guide": {"guide", "mentor", "woodcutter", "mage", "healer"},
}


def normalize_story_characters(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: Dict[str, str] = {}
    for raw_role, raw_description in value.items():
        role = str(raw_role).strip().lower()
        description = str(raw_description).strip()
        if not role or not description:
            continue
        normalized[role[:40]] = description[:500]
    return normalized


def extract_character_name(description: str) -> str:
    match = _QUOTED_NAME_PATTERN.search(description)
    if match:
        return match.group(1).strip()

    compact = " ".join(description.split())
    return compact[:40]


def _profile_key(profile: Dict[str, Any]) -> str:
    return str(profile.get("character_key") or "")


def _contains_term(text: str, term: str) -> bool:
    if re.fullmatch(r"[a-z][a-z ]*", term):
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    if term == "왕":
        return re.search(r"(?<!여)왕", text) is not None
    return term in text


def infer_character_gender(description: str) -> Optional[str]:
    text = " ".join(str(description).lower().split())
    scores = {
        gender: sum(_contains_term(text, term) for term in terms)
        for gender, terms in _GENDER_TERMS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0 or len({gender for gender, score in scores.items() if score == scores[best]}) > 1:
        return None
    return best


def infer_character_age_group(description: str) -> Optional[str]:
    text = " ".join(str(description).lower().split())
    scores = {
        age_group: sum(_contains_term(text, term) for term in terms)
        for age_group, terms in _AGE_TERMS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None
    tied = {age_group for age_group, score in scores.items() if score == scores[best]}
    if len(tied) == 1:
        return best

    # These pairs commonly overlap by wording (for example, "teenage girl").
    overlap_preferences = (
        ("teen", {"teen", "child"}),
        ("young_adult", {"young_adult", "adult"}),
        ("elder", {"elder", "adult"}),
    )
    for preferred, expected_tie in overlap_preferences:
        if tied == expected_tie and any(
            _contains_term(text, term) for term in _AGE_TERMS[preferred]
        ):
            return preferred
    return None


def _profile_rank(
    profile: Dict[str, Any],
    *,
    role: str,
    description: str,
    genre: Optional[str],
) -> tuple:
    normalized_genre = str(genre or "").strip().lower()
    genres = {str(item).strip().lower() for item in profile.get("genres") or []}
    role_tags = {
        str(item).strip().lower() for item in profile.get("role_tags") or []
    }
    tags = {
        str(item).strip().lower()
        for asset in profile.get("assets") or []
        for item in asset.get("tags") or []
    }
    role_hints = _ROLE_HINTS.get(role, set())
    inferred_gender = infer_character_gender(description)
    inferred_age_group = infer_character_age_group(description)
    profile_gender = str(profile.get("gender") or "").strip().lower()
    profile_age_group = str(profile.get("age_group") or "").strip().lower()

    semantic_score = 0
    if normalized_genre and normalized_genre in genres:
        semantic_score += 8
    semantic_score += 4 * len((tags | role_tags).intersection(role_hints))
    if role in role_tags:
        semantic_score += 10
    if inferred_gender:
        semantic_score += 30 if profile_gender == inferred_gender else -30
    if inferred_age_group:
        semantic_score += 18 if profile_age_group == inferred_age_group else -12
    digest = hashlib.sha256(
        f"{role}|{description}|{_profile_key(profile)}".encode("utf-8")
    ).hexdigest()
    return (-semantic_score, digest, _profile_key(profile))


def _default_face_asset(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    assets = profile.get("assets")
    if not isinstance(assets, list) or not assets:
        return None
    asset = next(
        (item for item in assets if item.get("pose") == "default"),
        assets[0],
    )
    return {
        "pose": asset.get("pose") or "default",
        "emotion": asset.get("emotion") or "neutral",
        "image_file_id": asset.get("image_file_id"),
        "image_url": asset.get("image_url"),
    }


def build_story_cast(
    characters: Any,
    profiles: Iterable[Dict[str, Any]],
    *,
    genre: Optional[str] = None,
    character_overrides: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    normalized = normalize_story_characters(characters)
    available = [
        profile
        for profile in profiles
        if profile.get("active", True)
        and _profile_key(profile)
        and isinstance(profile.get("assets"), list)
        and profile.get("assets")
    ]
    if not normalized or not available:
        return []

    overrides = {
        str(role).strip().lower(): str(character_key).strip().lower()
        for role, character_key in (character_overrides or {}).items()
        if str(role).strip() and str(character_key).strip()
    }
    profiles_by_key = {_profile_key(profile): profile for profile in available}

    roles = [role for role in ROLE_PRIORITY if role in normalized]
    roles.extend(
        sorted(
            role
            for role in set(normalized).difference(roles)
            if role not in NON_CHARACTER_ROLES
        )
    )
    unused_keys = {_profile_key(profile) for profile in available}
    cast: List[Dict[str, Any]] = []

    for role in roles:
        description = normalized[role]
        override_key = overrides.get(role)
        profile = profiles_by_key.get(override_key)
        is_user_selected = profile is not None
        if profile is None:
            candidates = [
                profile for profile in available if _profile_key(profile) in unused_keys
            ] or available
            profile = min(
                candidates,
                key=lambda item: _profile_rank(
                    item,
                    role=role,
                    description=description,
                    genre=genre,
                ),
            )
        character_key = _profile_key(profile)
        unused_keys.discard(character_key)
        cast.append(
            {
                "role": role,
                "name": extract_character_name(description),
                "source_description": description,
                "character_key": character_key,
                "profile_name": profile.get("name"),
                "gender": profile.get("gender"),
                "age_group": profile.get("age_group"),
                "role_tags": profile.get("role_tags") or [],
                "fixed_description": profile.get("description"),
                "style_prompt": profile.get("style_prompt"),
                "face_asset": _default_face_asset(profile),
                "selection_source": "user" if is_user_selected else "automatic",
            }
        )
    return cast


def select_story_cast_member(
    cast: Any,
    story_text: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(cast, list) or not cast:
        return None

    normalized_story = " ".join(str(story_text).lower().split())
    best_member = None
    best_score = 0
    for index, member in enumerate(cast):
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or "").strip().lower()
        source = str(member.get("source_description") or "").strip().lower()
        role = str(member.get("role") or "").strip().lower()
        score = 0
        if name and name in normalized_story:
            score += 20
        if source and source in normalized_story:
            score += 8
        if role and role in normalized_story:
            score += 3
        if role == "hero":
            score += 1
        if score > best_score:
            best_member = member
            best_score = score
        elif score == best_score and best_member is None and index == 0:
            best_member = member

    return best_member or next(
        (
            member
            for member in cast
            if isinstance(member, dict) and member.get("role") == "hero"
        ),
        cast[0],
    )
