from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKGROUND_ASSET_DIR = PROJECT_ROOT / "assets" / "backgrounds"

BACKGROUND_ASSETS = [
    {
        "key": "fantasy_castle",
        "genres": ["fantasy", "판타지", "마법"],
        "filename": "fantasy_castle.png",
        "scene_keywords": ["castle", "magic", "forest", "성", "마법", "숲"],
        "visual_tags": ["fantasy", "magic", "castle", "forest", "glowing_light"],
    },
    {
        "key": "adventure_ruins",
        "genres": ["adventure", "모험"],
        "filename": "adventure_ruins.png",
        "scene_keywords": ["mountain", "ruins", "journey", "산", "유적", "여행"],
        "visual_tags": ["adventure", "mountain", "ruins", "journey", "strong_wind"],
    },
    {
        "key": "nature_pond",
        "genres": ["nature", "자연", "힐링"],
        "filename": "nature_pond.png",
        "scene_keywords": ["pond", "meadow", "forest", "연못", "들판", "숲"],
        "visual_tags": ["nature", "pond", "meadow", "forest", "mist"],
    },
    {
        "key": "friendship_square",
        "genres": ["friendship", "우정", "감동"],
        "filename": "friendship_square.png",
        "scene_keywords": ["friend", "village", "park", "친구", "마을", "공원"],
        "visual_tags": ["friendship", "village", "park", "joyful"],
    },
    {
        "key": "mystery_library",
        "genres": ["mystery", "미스터리", "추리"],
        "filename": "mystery_library.png",
        "scene_keywords": ["library", "clue", "museum", "도서관", "단서", "박물관"],
        "visual_tags": ["mystery", "library", "clue", "shadow", "glowing_light"],
    },
]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def select_background_asset(
    genre: Optional[str],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    normalized_genre = _normalize(genre)
    normalized_story = _normalize(story_text)
    candidates = [
        asset
        for asset in BACKGROUND_ASSETS
        if normalized_genre
        and normalized_genre in {_normalize(item) for item in asset["genres"]}
    ]
    if not candidates:
        candidates = BACKGROUND_ASSETS

    best_asset = None
    best_score = -1
    for asset in candidates:
        path = BACKGROUND_ASSET_DIR / asset["filename"]
        if not path.is_file():
            continue
        genre_score = 3 if normalized_genre in {
            _normalize(item) for item in asset["genres"]
        } else 0
        keyword_score = sum(
            1
            for keyword in asset["scene_keywords"]
            if _normalize(keyword) in normalized_story
        )
        context = visual_context or {}
        direct_score = 8 if asset["key"] in context.get("background_keys", []) else 0
        context_tags = set(context.get("effect_tags", []))
        tag_score = 2 * len(context_tags.intersection(asset.get("visual_tags", [])))
        score = genre_score + keyword_score + direct_score + tag_score
        if score > best_score:
            best_asset = {**asset, "path": path}
            best_score = score

    return best_asset
