from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKGROUND_ASSET_DIR = PROJECT_ROOT / "assets" / "backgrounds"

GENRE_ALIASES = {
    "판타지": "fantasy",
    "마법": "fantasy",
    "모험": "adventure",
    "자연": "nature",
    "동물": "nature",
    "우정": "friendship",
    "감동": "friendship",
    "미스터리": "mystery",
    "추리": "mystery",
}

BACKGROUND_ASSETS = [
    {
        "key": "fantasy_castle",
        "genres": ["fantasy", "판타지", "마법"],
        "filename": "fantasy_castle.png",
        "video_filename": "fantasy_castle_wide_v2.png",
        "scene_keywords": ["castle", "magic", "forest", "성", "마법", "숲"],
        "visual_tags": ["fantasy", "magic", "castle", "forest", "glowing_light"],
    },
    {
        "key": "adventure_ruins",
        "genres": ["adventure", "모험"],
        "filename": "adventure_ruins.png",
        "video_filename": "adventure_ruins_wide_v2.png",
        "scene_keywords": ["mountain", "ruins", "journey", "산", "유적", "여행"],
        "visual_tags": ["adventure", "mountain", "ruins", "journey", "strong_wind"],
    },
    {
        "key": "nature_pond",
        "genres": ["nature", "자연", "힐링"],
        "filename": "nature_pond.png",
        "video_filename": "nature_pond_wide_v2.png",
        "scene_keywords": ["pond", "meadow", "forest", "연못", "들판", "숲"],
        "visual_tags": ["nature", "pond", "meadow", "forest", "mist"],
    },
    {
        "key": "friendship_square",
        "genres": ["friendship", "우정", "감동"],
        "filename": "friendship_square.png",
        "video_filename": "friendship_square_wide_v2.png",
        "scene_keywords": ["friend", "village", "park", "친구", "마을", "공원"],
        "visual_tags": ["friendship", "village", "park", "joyful"],
    },
    {
        "key": "mystery_library",
        "genres": ["mystery", "미스터리", "추리"],
        "filename": "mystery_library.png",
        "video_filename": "mystery_library_wide_v2.png",
        "scene_keywords": ["library", "clue", "museum", "도서관", "단서", "박물관"],
        "visual_tags": ["mystery", "library", "clue", "shadow", "glowing_light"],
    },
    {
        "key": "fantasy_crystal_cave",
        "genres": ["fantasy", "판타지", "마법"],
        "filename": "fantasy_crystal_cave_wide_v1.png",
        "video_filename": "fantasy_crystal_cave_wide_v1.png",
        "scene_keywords": [
            "crystal cave", "crystal", "cave", "portal",
            "수정 동굴", "수정", "동굴", "차원문", "마법문",
        ],
        "visual_tags": ["fantasy", "crystal", "cave", "portal", "glowing_light"],
    },
    {
        "key": "adventure_harbor",
        "genres": ["adventure", "모험"],
        "filename": "adventure_harbor_wide_v1.png",
        "video_filename": "adventure_harbor_wide_v1.png",
        "scene_keywords": [
            "harbor", "port", "sea", "ship", "lighthouse",
            "항구", "부두", "바다", "배", "선박", "등대",
        ],
        "visual_tags": ["adventure", "harbor", "sea", "ship", "sunlight"],
    },
    {
        "key": "nature_snowfield",
        "genres": ["nature", "adventure", "자연", "모험"],
        "filename": "nature_snowfield_wide_v1.png",
        "video_filename": "nature_snowfield_wide_v1.png",
        "scene_keywords": [
            "snow", "snowfield", "winter", "mountain pass", "cabin",
            "눈", "설원", "겨울", "눈길", "산길", "오두막",
        ],
        "visual_tags": ["nature", "snow", "winter", "mountain", "aurora"],
    },
    {
        "key": "friendship_festival",
        "genres": ["friendship", "우정", "감동"],
        "filename": "friendship_festival_wide_v1.png",
        "video_filename": "friendship_festival_wide_v1.png",
        "scene_keywords": [
            "festival", "celebration", "parade", "pavilion", "stage",
            "축제", "잔치", "행진", "정자", "무대",
        ],
        "visual_tags": ["friendship", "festival", "village", "joyful"],
    },
    {
        "key": "mystery_clocktower",
        "genres": ["mystery", "미스터리", "추리"],
        "filename": "mystery_clocktower_wide_v1.png",
        "video_filename": "mystery_clocktower_wide_v1.png",
        "scene_keywords": [
            "clocktower", "clock tower", "clock", "gear", "secret door",
            "시계탑", "시계", "톱니바퀴", "기어", "비밀문",
        ],
        "visual_tags": ["mystery", "clock", "gear", "secret_door", "moonlight"],
    },
]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_genre(value: Optional[str]) -> str:
    normalized = _normalize(value)
    return GENRE_ALIASES.get(normalized, normalized)


def select_background_asset(
    genre: Optional[str],
    story_text: str,
    visual_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    normalized_genre = _normalize_genre(genre)
    normalized_story = _normalize(story_text)
    candidates = [
        asset
        for asset in BACKGROUND_ASSETS
        if normalized_genre
        and normalized_genre in {_normalize_genre(item) for item in asset["genres"]}
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
            _normalize_genre(item) for item in asset["genres"]
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
            video_filename = asset.get("video_filename") or asset["filename"]
            video_path = BACKGROUND_ASSET_DIR / video_filename
            if not video_path.is_file():
                video_path = path
            best_asset = {
                **asset,
                "path": path,
                "video_path": video_path,
                "video_source": (
                    "panorama_asset"
                    if asset.get("video_filename")
                    else "standard_asset"
                ),
            }
            best_score = score

    return best_asset
