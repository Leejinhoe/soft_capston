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

ACTION_CYCLE_VARIANTS = (
    {
        "suffix": "fight_cycle_v2_sheet",
        "pose": "fighting",
        "emotion": "brave",
        "animation_group": "fight",
        "animation_layout": "3x2",
        "animation_frame_count": 6,
        "animation_version": 2,
        "animation_cycle_seconds": 3.0,
        "tags": ("action", "fight", "premium", "animation-cycle"),
        "keywords": (
            "fight",
            "battle",
            "attack",
            "sword",
            "\uc2f8\uc6b0",
            "\uc804\ud22c",
            "\uacf5\uaca9",
        ),
    },
    {
        "suffix": "walk_cycle_v1_sheet",
        "pose": "walking",
        "emotion": "determined",
        "animation_group": "walk",
        "animation_layout": "2x2",
        "animation_frame_count": 4,
        "animation_version": 1,
        "animation_cycle_seconds": 1.0,
        "tags": ("action", "walking", "premium", "animation-cycle"),
        "keywords": ("walk", "walking", "\uac77", "\uac78\uc5b4"),
    },
    {
        "suffix": "walk_cycle_v2_sheet",
        "pose": "walking",
        "emotion": "determined",
        "animation_group": "walk",
        "animation_layout": "2x1",
        "animation_frame_count": 2,
        "animation_version": 2,
        "animation_cycle_seconds": 1.4,
        "tags": (
            "action",
            "walking",
            "premium",
            "animation-cycle",
            "alternating-gait",
        ),
        "keywords": ("walk", "walking", "\uac77", "\uac78\uc5b4"),
    },
    {
        "suffix": "walk_cycle_v3_sheet",
        "pose": "walking",
        "emotion": "determined",
        "animation_group": "walk",
        "animation_layout": "3x2",
        "animation_frame_count": 6,
        "animation_version": 3,
        "animation_cycle_seconds": 1.2,
        "tags": (
            "action",
            "walking",
            "premium",
            "animation-cycle",
            "six-pose-gait",
            "identity-consistent",
        ),
        "keywords": ("walk", "walking", "journey", "\uac77", "\uac78\uc5b4"),
    },
    {
        "suffix": "run_cycle_v1_sheet",
        "pose": "running",
        "emotion": "determined",
        "animation_group": "run",
        "animation_layout": "3x2",
        "animation_frame_count": 6,
        "animation_version": 1,
        "animation_cycle_seconds": 0.8,
        "tags": ("action", "running", "premium", "animation-cycle"),
        "keywords": ("run", "running", "sprint", "\ub2ec\ub9ac", "\ub6f0"),
    },
    {
        "suffix": "jump_cycle_v1_sheet",
        "pose": "jumping",
        "emotion": "brave",
        "animation_group": "jump",
        "animation_layout": "3x2",
        "animation_frame_count": 6,
        "animation_version": 1,
        "animation_cycle_seconds": 2.4,
        "tags": ("action", "jump", "premium", "animation-cycle"),
        "keywords": ("jump", "leap", "hop", "\uc810\ud504", "\ub6f0\uc5b4"),
    },
    {
        "suffix": "jump_cycle_v2_sheet",
        "pose": "jumping",
        "emotion": "brave",
        "animation_group": "jump",
        "animation_layout": "3x3",
        "animation_frame_count": 9,
        "animation_version": 2,
        "animation_cycle_seconds": 2.7,
        "tags": (
            "action",
            "jump",
            "premium",
            "animation-cycle",
            "nine-pose-sequence",
            "clear-action-continuity",
        ),
        "keywords": ("jump", "leap", "hop", "\uc810\ud504", "\ub6f0\uc5b4"),
    },
    {
        "suffix": "magic_cycle_v1_sheet",
        "pose": "casting-magic",
        "emotion": "focused",
        "animation_group": "magic",
        "animation_layout": "3x2",
        "animation_frame_count": 6,
        "animation_version": 1,
        "animation_cycle_seconds": 3.0,
        "tags": ("action", "magic", "premium", "animation-cycle"),
        "keywords": ("magic", "spell", "cast", "\ub9c8\ubc95", "\uc8fc\ubb38"),
    },
    {
        "suffix": "magic_cycle_v2_sheet",
        "pose": "casting-magic",
        "emotion": "focused",
        "animation_group": "magic",
        "animation_layout": "3x3",
        "animation_frame_count": 9,
        "animation_version": 2,
        "animation_cycle_seconds": 2.8,
        "tags": (
            "action",
            "magic",
            "premium",
            "animation-cycle",
            "nine-pose-sequence",
            "clear-action-continuity",
        ),
        "keywords": ("magic", "spell", "cast", "\ub9c8\ubc95", "\uc8fc\ubb38"),
    },
    {
        "suffix": "fight_cycle_v1_sheet",
        "pose": "fighting",
        "emotion": "brave",
        "animation_group": "fight",
        "animation_layout": "2x2",
        "animation_frame_count": 4,
        "animation_version": 1,
        "animation_cycle_seconds": 3.0,
        "tags": ("action", "fight", "premium", "animation-cycle"),
        "keywords": (
            "fight",
            "battle",
            "attack",
            "sword",
            "\uc2f8\uc6b0",
            "\uc804\ud22c",
            "\uacf5\uaca9",
        ),
    },
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
    for variant in ACTION_CYCLE_VARIANTS:
        filename = f"{character_key}_{variant['suffix']}.png"
        if not (CHARACTER_ASSET_DIR / filename).is_file():
            continue
        specs.append(
            {
                "filename": filename,
                "pose": variant["pose"],
                "emotion": variant["emotion"],
                "quality_tier": "premium_action_cycle",
                "animation_group": variant["animation_group"],
                "animation_layout": variant["animation_layout"],
                "animation_frame_count": variant["animation_frame_count"],
                "animation_version": variant["animation_version"],
                "animation_cycle_seconds": variant["animation_cycle_seconds"],
                "tags": sorted(set(tags).union(variant["tags"])),
                "scene_keywords": list(variant["keywords"]),
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
        "male_01", "Minho", "male", "child",
        ["fantasy", "adventure"], ["hero", "warrior"],
        "Korean boy around age 8 with a round face, short black hair, bright brown eyes, "
        "a cobalt tunic, red scarf, leather belt, and small silver sword.",
    ),
    _profile(
        "male_02", "Jun", "male", "teen",
        ["adventure", "mystery"], ["hero", "explorer", "companion"],
        "Korean teenage boy with tousled dark hair, amber eyes, an ochre field jacket, "
        "navy trousers, canvas satchel, brass compass, and sturdy brown boots.",
    ),
    _profile(
        "male_03", "Taesan", "male", "adult",
        ["fantasy", "nature"], ["guardian", "guide", "warrior"],
        "Korean adult man with a broad kind face, tied-back black hair, a moss-green cloak, "
        "bronze shoulder guard, dark tunic, and carved wooden staff.",
    ),
    _profile(
        "male_04", "Doyun", "male", "elder",
        ["folktale", "adventure"], ["guide", "mentor", "woodcutter"],
        "Elderly Korean man with silver hair, short white beard, gentle wrinkles, "
        "a brown wool cap, forest-green vest, patched trousers, and an old rolled map.",
    ),
    _profile(
        "male_05", "Bori", "male", "child",
        ["nature", "friendship"], ["companion", "helper"],
        "Korean boy around age 7 with fluffy dark-brown hair, freckles, a leaf-green capelet, "
        "cream overalls, orange boots, and an acorn-shaped pouch.",
    ),
    _profile(
        "male_06", "Raven", "male", "young_adult",
        ["dark_fantasy", "mystery"], ["antagonist", "rival", "king"],
        "Young Korean man with a sharp pale face, long ink-black hair, gray eyes, "
        "a black-violet royal coat, silver crown, high boots, and a dark crystal ring.",
    ),
    _profile(
        "male_07", "Ian", "male", "child",
        ["royal", "friendship"], ["target", "prince", "companion"],
        "Korean boy around age 9 with neatly parted chestnut hair, warm brown eyes, "
        "an ivory prince jacket, sky-blue sash, gold trim, and white ankle boots.",
    ),
    _profile(
        "male_08", "Haneul", "male", "adult",
        ["fantasy", "mystery"], ["mage", "guide", "healer"],
        "Korean adult man with a slender face, wavy midnight hair, blue-gray eyes, "
        "a teal star-patterned robe, moon brooch, leather spellbook, and crystal wand.",
    ),
    _profile(
        "female_01", "Mina", "female", "child",
        ["fantasy", "adventure"], ["hero", "mage"],
        "Korean girl around age 8 with a round friendly face, short dark-brown bob, "
        "midnight-blue star cape, lavender tunic, brown boots, and glowing star wand.",
    ),
    _profile(
        "female_02", "Hana", "female", "child",
        ["friendship", "nature"], ["companion", "helper"],
        "Korean girl around age 8 with two low braids, bright brown eyes, "
        "a sunflower-yellow cardigan, denim-blue overalls, coral shoes, and friendship bracelet.",
    ),
    _profile(
        "female_03", "Miran", "female", "teen",
        ["royal", "fantasy"], ["target", "princess", "healer"],
        "Korean teenage girl with a soft oval face, long chestnut hair, hazel eyes, "
        "a rose-pink royal dress, pearl circlet, cream cape, and golden key necklace.",
    ),
    _profile(
        "female_04", "Luna", "female", "young_adult",
        ["fantasy", "nature"], ["companion", "guide", "fairy"],
        "Young Korean woman with a heart-shaped face, wavy silver-brown hair, green eyes, "
        "a leaf-layered emerald dress, translucent wings, vine belt, and glowing lantern.",
    ),
    _profile(
        "female_05", "Seoyeon", "female", "adult",
        ["adventure", "mystery"], ["hero", "explorer", "detective"],
        "Korean adult woman with a confident oval face, black hair in a low ponytail, "
        "an amber scarf, navy expedition coat, charcoal trousers, notebook, and magnifying glass.",
    ),
    _profile(
        "female_06", "Arin", "female", "elder",
        ["folktale", "fantasy"], ["guide", "mentor", "healer"],
        "Elderly Korean woman with silver hair in a low bun, warm smile lines, "
        "a plum shawl, cream hanbok-inspired dress, herb pouch, and carved willow cane.",
    ),
    _profile(
        "female_07", "Nara", "female", "young_adult",
        ["dark_fantasy", "royal"], ["antagonist", "rival", "queen"],
        "Young Korean woman with an angular face, long raven hair, violet eyes, "
        "a burgundy-black royal gown, obsidian crown, silver shoulder cape, and dark mirror.",
    ),
    _profile(
        "female_08", "Sol", "female", "teen",
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
    is_premium_cycle = quality_tier == "premium_action_cycle"
    is_generated_asset = is_premium_reference or is_premium_cycle
    provider = "openai-imagegen" if is_generated_asset else "local-procedural"
    if is_premium_reference:
        model = "storybook-character-reference-v2"
    elif is_premium_cycle:
        model = "storybook-character-action-cycle-v1"
    else:
        model = "storybook-character-vector-v1"
    asset_role = (
        "character_action_cycle" if is_premium_cycle else "character_reference"
    )
    files_collection = database.get_collection(f"{MEDIA_GRIDFS_BUCKET}.files")
    existing = await files_collection.find_one(
        {
            "metadata.asset_role": asset_role,
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
                "asset_role": asset_role,
                "character_key": character["character_key"],
                "pose": asset["pose"],
                "emotion": asset["emotion"],
                "quality_tier": quality_tier,
                "animation_group": asset.get("animation_group"),
                "animation_layout": asset.get("animation_layout"),
                "animation_frame_count": asset.get("animation_frame_count"),
                "animation_version": asset.get("animation_version"),
                "animation_cycle_seconds": asset.get("animation_cycle_seconds"),
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
                    "animation_group": asset_spec.get("animation_group"),
                    "animation_layout": asset_spec.get("animation_layout"),
                    "animation_frame_count": asset_spec.get(
                        "animation_frame_count"
                    ),
                    "animation_version": asset_spec.get("animation_version"),
                    "animation_cycle_seconds": asset_spec.get(
                        "animation_cycle_seconds"
                    ),
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
