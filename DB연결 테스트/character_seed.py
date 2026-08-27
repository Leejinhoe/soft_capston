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

MOTION_SHEET_VARIANT = {
    "pose": "motion-sheet",
    "emotion": "dynamic",
    "quality_tier": "video_motion_sheet_v3",
    "tags": ("video", "motion-sheet", "action"),
    "scene_keywords": (),
    "sheet_columns": 4,
    "sheet_rows": 2,
    "motion_cells": {
        "idle": [0],
        "walking": [1, 2],
        "running": [3],
        "magic": [4],
        "battle": [5],
        "rescue": [6],
        "talking": [7],
    },
}
TARGET_JOURNEY_SHEET_VARIANT = {
    "pose": "target-journey-sheet",
    "emotion": "determined",
    "quality_tier": "video_target_journey_sheet_v4",
    "tags": ("video", "motion-sheet", "rear-view", "target-journey"),
    "scene_keywords": ("castle", "tower", "forest path", "\uc131", "\ud0d1", "\uc232\uae38"),
    "sheet_columns": 4,
    "sheet_rows": 2,
    "motion_cells": {
        "target_running": list(range(8)),
    },
}
RUN_CYCLE_SHEET_VARIANT = {
    "pose": "run-cycle-sheet",
    "emotion": "determined",
    "quality_tier": "video_run_cycle_v16",
    "tags": ("video", "sprite-sheet", "rear-view", "running"),
    "scene_keywords": ("run", "running", "castle", "달리", "성"),
    "sheet_columns": 4,
    "sheet_rows": 2,
    "motion_cells": {
        "target_running": list(range(8)),
    },
    "playback": "discrete-frames",
}
JUMP_CYCLE_SHEET_VARIANT = {
    "pose": "jump-cycle-sheet",
    "emotion": "determined",
    "quality_tier": "video_jump_cycle_v28",
    "tags": ("video", "sprite-sheet", "jumping", "identity-locked", "derived-action-v28"),
    "scene_keywords": ("jump", "leap", "hop", "\uc810\ud504", "\ub3c4\uc57d"),
    "sheet_columns": 4,
    "sheet_rows": 2,
    "motion_cells": {"jumping": list(range(8))},
    "playback": "discrete-frames",
}
JUMP_CYCLE_SHEET_LEGACY_VARIANT = {
    **JUMP_CYCLE_SHEET_VARIANT,
    "quality_tier": "video_jump_cycle_v23",
    "tags": ("video", "sprite-sheet", "jumping", "identity-locked", "derived-action-v23"),
}
ACTION_SHEET_VARIANT = {
    "pose": "action-sheet",
    "emotion": "dynamic",
    "quality_tier": "video_action_sheet_v28",
    "tags": ("video", "sprite-sheet", "actions", "identity-locked", "derived-action-v28"),
    "scene_keywords": (
        "wave", "investigate", "handoff", "rescue", "magic", "battle",
    ),
    "sheet_columns": 4,
    "sheet_rows": 2,
    "motion_cells": {
        "idle": [0], "wave": [1], "investigate": [2], "handoff": [3],
        "magic": [4, 5], "battle": [6, 7],
    },
    "playback": "discrete-frames",
}
ACTION_SHEET_LEGACY_VARIANT = {
    **ACTION_SHEET_VARIANT,
    "quality_tier": "video_action_sheet_v23",
    "tags": ("video", "sprite-sheet", "actions", "identity-locked", "derived-action-v23"),
}
ACTION_CYCLE_VARIANTS = {
    "battle": {
        "pose": "battle-cycle-sheet",
        "emotion": "determined",
        "quality_tier": "video_battle_cycle_v28",
        "tags": ("video", "sprite-sheet", "battle", "identity-locked", "derived-action-v28"),
        "filename_version": "v28",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"battle": list(range(8))},
        "playback": "optical-flow-adjacent-frames",
    },
    "magic": {
        "pose": "magic-cycle-sheet",
        "emotion": "focused",
        "quality_tier": "video_magic_cycle_v22",
        "tags": ("video", "sprite-sheet", "magic", "identity-locked"),
        "filename_version": "v22",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"magic": list(range(8))},
        "playback": "optical-flow-adjacent-frames",
    },
    "interaction": {
        "pose": "interaction-cycle-sheet",
        "emotion": "helpful",
        "quality_tier": "video_interaction_cycle_v28",
        "tags": ("video", "sprite-sheet", "interaction", "identity-locked", "derived-action-v28"),
        "filename_version": "v28",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"interaction": list(range(8))},
        "playback": "optical-flow-adjacent-frames",
    },
    "sit": {
        "pose": "sit-cycle-sheet",
        "emotion": "calm",
        "quality_tier": "video_sit_cycle_v1",
        "tags": ("video", "sprite-sheet", "sitting", "identity-locked"),
        "filename_version": "v1",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"sit": list(range(8))},
        "playback": "optical-flow-adjacent-frames",
    },
    "stand": {
        "pose": "stand-cycle-sheet",
        "emotion": "calm",
        "quality_tier": "video_stand_cycle_v1",
        "tags": ("video", "sprite-sheet", "standing", "identity-locked"),
        "filename_version": "v1",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"stand": list(range(8))},
        "playback": "optical-flow-adjacent-frames",
    },
    "crawl": {
        "pose": "crawl-cycle-sheet",
        "emotion": "focused",
        "quality_tier": "video_crawl_cycle_v2",
        "tags": ("video", "sprite-sheet", "crawling", "identity-locked", "derived-pose-v2"),
        "filename_version": "v2",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"crawl": list(range(8))},
        "playback": "discrete-frames",
    },
    "climb": {
        "pose": "climb-cycle-sheet",
        "emotion": "focused",
        "quality_tier": "video_climb_cycle_v2",
        "tags": ("video", "sprite-sheet", "climbing", "identity-locked", "derived-pose-v2"),
        "filename_version": "v2",
        "sheet_columns": 4,
        "sheet_rows": 2,
        "motion_cells": {"climb": list(range(8))},
        "playback": "discrete-frames",
    },
}


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
    motion_filename = f"motion_sheets/{character_key}_motion_sheet_v3.png"
    if (CHARACTER_ASSET_DIR / motion_filename).is_file():
        specs.append(
            {
                "filename": motion_filename,
                "pose": MOTION_SHEET_VARIANT["pose"],
                "emotion": MOTION_SHEET_VARIANT["emotion"],
                "quality_tier": MOTION_SHEET_VARIANT["quality_tier"],
                "tags": sorted(set(tags).union(MOTION_SHEET_VARIANT["tags"])),
                "scene_keywords": list(MOTION_SHEET_VARIANT["scene_keywords"]),
                "sheet_columns": MOTION_SHEET_VARIANT["sheet_columns"],
                "sheet_rows": MOTION_SHEET_VARIANT["sheet_rows"],
                "motion_cells": dict(MOTION_SHEET_VARIANT["motion_cells"]),
            }
        )
    target_journey_filename = (
        f"motion_sheets/{character_key}_target_journey_sheet_v4.png"
    )
    if (CHARACTER_ASSET_DIR / target_journey_filename).is_file():
        specs.append(
            {
                "filename": target_journey_filename,
                "pose": TARGET_JOURNEY_SHEET_VARIANT["pose"],
                "emotion": TARGET_JOURNEY_SHEET_VARIANT["emotion"],
                "quality_tier": TARGET_JOURNEY_SHEET_VARIANT["quality_tier"],
                "tags": sorted(
                    set(tags).union(TARGET_JOURNEY_SHEET_VARIANT["tags"])
                ),
                "scene_keywords": list(
                    TARGET_JOURNEY_SHEET_VARIANT["scene_keywords"]
                ),
                "sheet_columns": TARGET_JOURNEY_SHEET_VARIANT["sheet_columns"],
                "sheet_rows": TARGET_JOURNEY_SHEET_VARIANT["sheet_rows"],
                "motion_cells": dict(
                    TARGET_JOURNEY_SHEET_VARIANT["motion_cells"]
                ),
            }
        )
    run_cycle_filename = f"motion_sheets/{character_key}_run_cycle_v16.png"
    if (CHARACTER_ASSET_DIR / run_cycle_filename).is_file():
        specs.append(
            {
                "filename": run_cycle_filename,
                "pose": RUN_CYCLE_SHEET_VARIANT["pose"],
                "emotion": RUN_CYCLE_SHEET_VARIANT["emotion"],
                "quality_tier": RUN_CYCLE_SHEET_VARIANT["quality_tier"],
                "tags": sorted(
                    set(tags).union(RUN_CYCLE_SHEET_VARIANT["tags"])
                ),
                "scene_keywords": list(
                    RUN_CYCLE_SHEET_VARIANT["scene_keywords"]
                ),
                "sheet_columns": RUN_CYCLE_SHEET_VARIANT["sheet_columns"],
                "sheet_rows": RUN_CYCLE_SHEET_VARIANT["sheet_rows"],
                "motion_cells": dict(RUN_CYCLE_SHEET_VARIANT["motion_cells"]),
                "playback": RUN_CYCLE_SHEET_VARIANT["playback"],
            }
        )
    jump_cycle_filename = f"motion_sheets/{character_key}_jump_cycle_v28.png"
    jump_cycle_variant = JUMP_CYCLE_SHEET_VARIANT
    if not (CHARACTER_ASSET_DIR / jump_cycle_filename).is_file():
        jump_cycle_filename = f"motion_sheets/{character_key}_jump_cycle_v23.png"
        jump_cycle_variant = JUMP_CYCLE_SHEET_LEGACY_VARIANT
    if (CHARACTER_ASSET_DIR / jump_cycle_filename).is_file():
        specs.append(
            {
                "filename": jump_cycle_filename,
                "pose": jump_cycle_variant["pose"],
                "emotion": jump_cycle_variant["emotion"],
                "quality_tier": jump_cycle_variant["quality_tier"],
                "tags": sorted(
                    set(tags).union(jump_cycle_variant["tags"])
                ),
                "scene_keywords": list(
                    jump_cycle_variant["scene_keywords"]
                ),
                "sheet_columns": jump_cycle_variant["sheet_columns"],
                "sheet_rows": jump_cycle_variant["sheet_rows"],
                "motion_cells": dict(jump_cycle_variant["motion_cells"]),
                "playback": jump_cycle_variant["playback"],
            }
        )
    action_sheet_filename = f"motion_sheets/{character_key}_action_sheet_v28.png"
    action_sheet_variant = ACTION_SHEET_VARIANT
    if not (CHARACTER_ASSET_DIR / action_sheet_filename).is_file():
        action_sheet_filename = f"motion_sheets/{character_key}_action_sheet_v23.png"
        action_sheet_variant = ACTION_SHEET_LEGACY_VARIANT
    if (CHARACTER_ASSET_DIR / action_sheet_filename).is_file():
        specs.append(
            {
                "filename": action_sheet_filename,
                "pose": action_sheet_variant["pose"],
                "emotion": action_sheet_variant["emotion"],
                "quality_tier": action_sheet_variant["quality_tier"],
                "tags": sorted(set(tags).union(action_sheet_variant["tags"])),
                "scene_keywords": list(action_sheet_variant["scene_keywords"]),
                "sheet_columns": action_sheet_variant["sheet_columns"],
                "sheet_rows": action_sheet_variant["sheet_rows"],
                "motion_cells": dict(action_sheet_variant["motion_cells"]),
                "playback": action_sheet_variant["playback"],
            }
        )
    for action_name, variant in ACTION_CYCLE_VARIANTS.items():
        selected_variant = variant
        cycle_filename = f"motion_sheets/{character_key}_{action_name}_cycle_{variant['filename_version']}.png"
        if action_name in {"sit", "stand"} and (
            CHARACTER_ASSET_DIR
            / f"motion_sheets/{character_key}_{action_name}_cycle_v2.png"
        ).is_file():
            selected_variant = {
                **variant,
                "quality_tier": f"video_{action_name}_cycle_v2",
                "filename_version": "v2",
                "tags": tuple(
                    "derived-pose-v2" if tag == "identity-locked" else tag
                    for tag in variant["tags"]
                ),
            }
            cycle_filename = f"motion_sheets/{character_key}_{action_name}_cycle_v2.png"
        if not (CHARACTER_ASSET_DIR / cycle_filename).is_file() and action_name in {
            "battle", "interaction",
        }:
            selected_variant = {
                **variant,
                "quality_tier": f"video_{action_name}_cycle_v23",
                "filename_version": "v23",
                "tags": tuple(
                    "derived-action-v23" if tag == "derived-action-v28" else tag
                    for tag in variant["tags"]
                ),
            }
            cycle_filename = f"motion_sheets/{character_key}_{action_name}_cycle_v23.png"
        if not (CHARACTER_ASSET_DIR / cycle_filename).is_file():
            continue
        specs.append(
            {
                "filename": cycle_filename,
                "pose": selected_variant["pose"],
                "emotion": selected_variant["emotion"],
                "quality_tier": selected_variant["quality_tier"],
                "tags": sorted(set(tags).union(selected_variant["tags"])),
                "scene_keywords": [action_name],
                "sheet_columns": selected_variant["sheet_columns"],
                "sheet_rows": selected_variant["sheet_rows"],
                "motion_cells": dict(selected_variant["motion_cells"]),
                "playback": selected_variant["playback"],
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
    is_target_journey_sheet = quality_tier == "video_target_journey_sheet_v4"
    is_run_cycle_sheet = quality_tier == "video_run_cycle_v16"
    is_jump_cycle_sheet = quality_tier in {
        "video_jump_cycle_v28", "video_jump_cycle_v23", "video_jump_cycle_v20",
    }
    is_action_sheet = quality_tier in {
        "video_action_sheet_v28", "video_action_sheet_v23", "video_action_sheet_v21",
    }
    is_action_cycle_sheet = quality_tier in {
        "video_battle_cycle_v28",
        "video_battle_cycle_v23",
        "video_battle_cycle_v22",
        "video_magic_cycle_v22",
        "video_interaction_cycle_v28",
        "video_interaction_cycle_v23",
        "video_interaction_cycle_v22",
        "video_sit_cycle_v1",
        "video_stand_cycle_v1",
        "video_sit_cycle_v2",
        "video_stand_cycle_v2",
        "video_crawl_cycle_v2",
        "video_climb_cycle_v2",
    }
    is_motion_sheet = (
        quality_tier == "video_motion_sheet_v3"
        or is_target_journey_sheet
        or is_run_cycle_sheet
        or is_jump_cycle_sheet
        or is_action_sheet
        or is_action_cycle_sheet
    )
    provider = (
        "openai-imagegen"
        if is_premium_reference or is_motion_sheet
        else "local-procedural"
    )
    model = (
        (
            (
                (
                    "storybook-posture-cycle-sheet-v2"
                    if quality_tier in {
                        "video_sit_cycle_v2", "video_stand_cycle_v2"
                    }
                    else "storybook-posture-cycle-sheet-v1"
                    if quality_tier in {
                        "video_sit_cycle_v1", "video_stand_cycle_v1"
                    }
                    else (
                        "storybook-scene-pose-cycle-sheet-v2"
                        if quality_tier in {
                            "video_crawl_cycle_v2", "video_climb_cycle_v2"
                        }
                        else (
                            "storybook-action-cycle-sheet-v28"
                            if quality_tier in {
                                "video_battle_cycle_v28",
                                "video_interaction_cycle_v28",
                            }
                            else "storybook-action-cycle-sheet-v23"
                        )
                    )
                )
                if is_action_cycle_sheet
                else (
                    "storybook-action-sheet-v28"
                    if quality_tier == "video_action_sheet_v28"
                    else "storybook-action-sheet-v23"
                )
                if is_action_sheet
                else (
                    "storybook-jump-cycle-sheet-v28"
                    if quality_tier == "video_jump_cycle_v28"
                    else "storybook-jump-cycle-sheet-v23"
                )
                if is_jump_cycle_sheet
                else "storybook-run-cycle-sheet-v16"
                if is_run_cycle_sheet
                else "storybook-target-journey-sheet-v4"
            )
            if is_target_journey_sheet or is_run_cycle_sheet or is_jump_cycle_sheet or is_action_sheet or is_action_cycle_sheet
            else "storybook-character-motion-sheet-v3"
        )
        if is_motion_sheet
        else (
            "storybook-character-reference-v2"
            if is_premium_reference
            else "storybook-character-vector-v1"
        )
    )
    asset_role = (
        "character_action_cycle_sheet"
        if is_action_cycle_sheet
        else "character_action_sheet"
        if is_action_sheet
        else "character_jump_cycle_sheet"
        if is_jump_cycle_sheet
        else (
            "character_run_cycle_sheet"
            if is_run_cycle_sheet
            else (
                "character_target_journey_sheet"
                if is_target_journey_sheet
                else (
                    "character_motion_sheet"
                    if is_motion_sheet
                    else "character_reference"
                )
            )
        )
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
                "provider": provider,
                "model": model,
                "sha256": sha256,
                "sheet_columns": asset.get("sheet_columns"),
                "sheet_rows": asset.get("sheet_rows"),
                "motion_cells": asset.get("motion_cells"),
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
            stored_asset = {
                "pose": asset_spec["pose"],
                "emotion": asset_spec["emotion"],
                "image_file_id": stored["file_id"],
                "image_url": stored["url"],
                "quality_tier": asset_spec.get("quality_tier", "fast_action"),
                "tags": asset_spec["tags"],
                "scene_keywords": asset_spec["scene_keywords"],
            }
            for key in (
                "sheet_columns",
                "sheet_rows",
                "motion_cells",
                "playback",
            ):
                if key in asset_spec:
                    stored_asset[key] = asset_spec[key]
            stored_assets.append(stored_asset)
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
