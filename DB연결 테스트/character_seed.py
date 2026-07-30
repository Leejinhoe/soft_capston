import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from database import (
    MEDIA_GRIDFS_BUCKET,
    character_profiles_collection,
    database,
    media_files_bucket,
)
from media_queue import build_media_file_url, serialize_object_id

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARACTER_ASSET_DIR = PROJECT_ROOT / "assets" / "characters"
COMMON_STYLE = (
    "polished soft watercolor and gouache children's book illustration, "
    "rounded shapes, clean silhouette, expressive eyes, warm cinematic color"
)

ASSET_VARIANTS = (
    ("default", "default", "neutral", ("portrait", "reference"), ()),
    ("happy", "default", "happy", ("expression", "happy"), ("happy", "smile", "joy")),
    ("sad", "default", "sad", ("expression", "sad"), ("sad", "cry", "lonely")),
    ("angry", "default", "angry", ("expression", "angry"), ("angry", "fight", "conflict")),
    ("walking", "walking", "determined", ("action", "walking"), ("walk", "journey", "travel")),
    ("talking", "talking", "friendly", ("action", "talking"), ("talk", "speak", "conversation")),
    ("magic", "casting-magic", "focused", ("action", "magic"), ("magic", "spell", "power")),
    ("rescue", "rescuing", "brave", ("action", "rescue"), ("help", "rescue", "protect")),
)

REFERENCE_VARIANT = (
    "reference_v2",
    "default",
    "neutral",
    ("portrait", "reference", "premium"),
    (),
)


def _asset_specs(character_key: str, tags: List[str]) -> List[Dict[str, Any]]:
    specs = []
    reference_filename = f"{character_key}_{REFERENCE_VARIANT[0]}.png"
    if (CHARACTER_ASSET_DIR / reference_filename).is_file():
        _, pose, emotion, variant_tags, keywords = REFERENCE_VARIANT
        specs.append(
            {
                "filename": reference_filename,
                "pose": pose,
                "emotion": emotion,
                "quality_tier": "premium_reference",
                "tags": sorted(set(tags).union(variant_tags)),
                "scene_keywords": list(keywords),
            }
        )
    for suffix, pose, emotion, variant_tags, keywords in ASSET_VARIANTS:
        specs.append(
            {
                "filename": f"{character_key}_{suffix}.png",
                "pose": pose,
                "emotion": emotion,
                "quality_tier": "fast_action",
                "tags": sorted(set(tags).union(variant_tags)),
                "scene_keywords": list(keywords),
            }
        )
    return specs


def _profile(
    character_key: str,
    name: str,
    gender: str,
    age_group: str,
    genres: List[str],
    role_tags: List[str],
    description: str,
) -> Dict[str, Any]:
    base_tags = [gender, age_group, *genres, *role_tags]
    return {
        "character_key": character_key,
        "name": name,
        "gender": gender,
        "age_group": age_group,
        "genres": genres,
        "role_tags": role_tags,
        "description": description,
        "assets": _asset_specs(character_key, base_tags),
    }


DEFAULT_CHARACTERS: List[Dict[str, Any]] = [
    _profile(
        "male_01", "민호", "male", "child",
        ["fantasy", "adventure"], ["hero", "warrior"],
        "Korean boy around age 8 with a round face, short black hair, bright brown eyes, "
        "a cobalt tunic, red scarf, leather belt, and small silver sword.",
    ),
    _profile(
        "male_02", "준", "male", "teen",
        ["adventure", "mystery"], ["hero", "explorer", "companion"],
        "Korean teenage boy with tousled dark hair, amber eyes, an ochre field jacket, "
        "navy trousers, canvas satchel, brass compass, and sturdy brown boots.",
    ),
    _profile(
        "male_03", "태산", "male", "adult",
        ["fantasy", "nature"], ["guardian", "guide", "warrior"],
        "Korean adult man with a broad kind face, tied-back black hair, a moss-green cloak, "
        "bronze shoulder guard, dark tunic, and carved wooden staff.",
    ),
    _profile(
        "male_04", "도윤", "male", "elder",
        ["folktale", "adventure"], ["guide", "mentor", "woodcutter"],
        "Elderly Korean man with silver hair, short white beard, gentle wrinkles, "
        "a brown wool cap, forest-green vest, patched trousers, and an old rolled map.",
    ),
    _profile(
        "male_05", "보리", "male", "child",
        ["nature", "friendship"], ["companion", "helper"],
        "Korean boy around age 7 with fluffy dark-brown hair, freckles, a leaf-green capelet, "
        "cream overalls, orange boots, and an acorn-shaped pouch.",
    ),
    _profile(
        "male_06", "레이븐", "male", "young_adult",
        ["dark_fantasy", "mystery"], ["antagonist", "rival", "king"],
        "Young Korean man with a sharp pale face, long ink-black hair, gray eyes, "
        "a black-violet royal coat, silver crown, high boots, and a dark crystal ring.",
    ),
    _profile(
        "male_07", "이안", "male", "child",
        ["royal", "friendship"], ["target", "prince", "companion"],
        "Korean boy around age 9 with neatly parted chestnut hair, warm brown eyes, "
        "an ivory prince jacket, sky-blue sash, gold trim, and white ankle boots.",
    ),
    _profile(
        "male_08", "하늘", "male", "adult",
        ["fantasy", "mystery"], ["mage", "guide", "healer"],
        "Korean adult man with a slender face, wavy midnight hair, blue-gray eyes, "
        "a teal star-patterned robe, moon brooch, leather spellbook, and crystal wand.",
    ),
    _profile(
        "female_01", "미나", "female", "child",
        ["fantasy", "adventure"], ["hero", "mage"],
        "Korean girl around age 8 with a round friendly face, short dark-brown bob, "
        "midnight-blue star cape, lavender tunic, brown boots, and glowing star wand.",
    ),
    _profile(
        "female_02", "하나", "female", "child",
        ["friendship", "nature"], ["companion", "helper"],
        "Korean girl around age 8 with two low braids, bright brown eyes, "
        "a sunflower-yellow cardigan, denim-blue overalls, coral shoes, and friendship bracelet.",
    ),
    _profile(
        "female_03", "미란", "female", "teen",
        ["royal", "fantasy"], ["target", "princess", "healer"],
        "Korean teenage girl with a soft oval face, long chestnut hair, hazel eyes, "
        "a rose-pink royal dress, pearl circlet, cream cape, and golden key necklace.",
    ),
    _profile(
        "female_04", "루나", "female", "young_adult",
        ["fantasy", "nature"], ["companion", "guide", "fairy"],
        "Young Korean woman with a heart-shaped face, wavy silver-brown hair, green eyes, "
        "a leaf-layered emerald dress, translucent wings, vine belt, and glowing lantern.",
    ),
    _profile(
        "female_05", "서연", "female", "adult",
        ["adventure", "mystery"], ["hero", "explorer", "detective"],
        "Korean adult woman with a confident oval face, black hair in a low ponytail, "
        "an amber scarf, navy expedition coat, charcoal trousers, notebook, and magnifying glass.",
    ),
    _profile(
        "female_06", "아린", "female", "elder",
        ["folktale", "fantasy"], ["guide", "mentor", "healer"],
        "Elderly Korean woman with silver hair in a low bun, warm smile lines, "
        "a plum shawl, cream hanbok-inspired dress, herb pouch, and carved willow cane.",
    ),
    _profile(
        "female_07", "나라", "female", "young_adult",
        ["dark_fantasy", "royal"], ["antagonist", "rival", "queen"],
        "Young Korean woman with an angular face, long raven hair, violet eyes, "
        "a burgundy-black royal gown, obsidian crown, silver shoulder cape, and dark mirror.",
    ),
    _profile(
        "female_08", "솔", "female", "teen",
        ["nature", "friendship"], ["guardian", "companion", "archer"],
        "Korean teenage girl with a sun-kissed round face, wavy dark-brown hair, "
        "a moss cape, leaf-pattern cream tunic, forest boots, acorn pendant, and short bow.",
    ),
]


async def _store_character_asset(
    character: Dict[str, Any],
    asset: Dict[str, Any],
) -> Dict[str, str]:
    asset_path = CHARACTER_ASSET_DIR / asset["filename"]
    if not asset_path.is_file():
        raise FileNotFoundError(f"Character asset not found: {asset_path}")

    content = await asyncio.to_thread(asset_path.read_bytes)
    sha256 = hashlib.sha256(content).hexdigest()
    quality_tier = asset.get("quality_tier", "fast_action")
    is_premium_reference = quality_tier == "premium_reference"
    provider = "openai-imagegen" if is_premium_reference else "local-procedural"
    model = (
        "storybook-character-reference-v2"
        if is_premium_reference
        else "storybook-character-vector-v1"
    )
    files_collection = database.get_collection(f"{MEDIA_GRIDFS_BUCKET}.files")
    existing = await files_collection.find_one(
        {
            "metadata.asset_role": "character_reference",
            "metadata.character_key": character["character_key"],
            "metadata.sha256": sha256,
        }
    )
    if existing:
        file_id = existing["_id"]
    else:
        file_id = await media_files_bucket.upload_from_stream(
            f"character_{character['character_key']}_{sha256[:12]}.png",
            content,
            metadata={
                "content_type": "image/png",
                "media_kind": "image",
                "asset_role": "character_reference",
                "character_key": character["character_key"],
                "pose": asset["pose"],
                "emotion": asset["emotion"],
                "quality_tier": quality_tier,
                "provider": provider,
                "model": model,
                "sha256": sha256,
                "created_at": datetime.utcnow().isoformat(),
            },
        )

    file_id_text = serialize_object_id(file_id)
    return {
        "file_id": file_id_text,
        "url": build_media_file_url(file_id_text, "image"),
    }


async def seed_default_character_profiles() -> int:
    seeded_count = 0
    active_character_keys = [
        character["character_key"] for character in DEFAULT_CHARACTERS
    ]
    await character_profiles_collection.update_many(
        {
            "seeded": True,
            "character_key": {"$nin": active_character_keys},
        },
        {
            "$set": {
                "active": False,
                "replaced_by_catalog": "gender-balanced-v1",
                "updated_at": datetime.utcnow(),
            }
        },
    )
    for character in DEFAULT_CHARACTERS:
        stored_assets = []
        for asset_spec in character["assets"]:
            try:
                stored = await _store_character_asset(character, asset_spec)
            except FileNotFoundError as exc:
                logger.warning("%s", exc)
                continue
            stored_assets.append(
                {
                    "pose": asset_spec["pose"],
                    "emotion": asset_spec["emotion"],
                    "image_file_id": stored["file_id"],
                    "image_url": stored["url"],
                    "quality_tier": asset_spec.get("quality_tier", "fast_action"),
                    "tags": asset_spec["tags"],
                    "scene_keywords": asset_spec["scene_keywords"],
                }
            )
        if not stored_assets:
            continue

        now = datetime.utcnow()
        await character_profiles_collection.update_one(
            {"character_key": character["character_key"]},
            {
                "$set": {
                    "name": character["name"],
                    "gender": character["gender"],
                    "age_group": character["age_group"],
                    "role_tags": character["role_tags"],
                    "description": character["description"],
                    "style_prompt": COMMON_STYLE,
                    "genres": sorted({genre.lower() for genre in character["genres"]}),
                    "assets": stored_assets,
                    "active": True,
                    "seeded": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        seeded_count += 1

    return seeded_count
