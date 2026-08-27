import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import character_seed
from character_seed import (
    ACTION_CYCLE_VARIANTS,
    ACTION_SHEET_VARIANT,
    DEFAULT_CHARACTERS,
    JUMP_CYCLE_SHEET_VARIANT,
    seed_default_character_profiles,
)
from story_cast import (
    build_story_cast,
    infer_character_age_group,
    infer_character_gender,
)


EXPECTED_SUFFIXES = (
    "default",
    "happy",
    "sad",
    "angry",
    "walking",
    "talking",
    "magic",
    "rescue",
)

PREMIUM_REFERENCE_KEYS = {
    *(f"male_{index:02d}" for index in range(1, 9)),
    *(f"female_{index:02d}" for index in range(1, 9)),
}
MOTION_SHEET_KEYS = PREMIUM_REFERENCE_KEYS
TARGET_JOURNEY_KEYS = PREMIUM_REFERENCE_KEYS
RUN_CYCLE_KEYS = PREMIUM_REFERENCE_KEYS
JUMP_CYCLE_KEYS = PREMIUM_REFERENCE_KEYS
ACTION_SHEET_KEYS = PREMIUM_REFERENCE_KEYS
ACTION_CYCLE_KEYS = {"male_01"}
DEDICATED_ACTION_CYCLE_KEYS = PREMIUM_REFERENCE_KEYS


def _runtime_profile(profile):
    result = dict(profile)
    result["active"] = True
    result["style_prompt"] = "storybook"
    result["assets"] = [
        {
            **asset,
            "image_file_id": f"{profile['character_key']}-{index}",
            "image_url": f"/images/{profile['character_key']}-{index}",
        }
        for index, asset in enumerate(profile["assets"])
    ]
    return result


class CharacterCatalogTests(unittest.TestCase):
    def test_v28_action_contract_is_consistent(self):
        self.assertEqual(
            JUMP_CYCLE_SHEET_VARIANT["quality_tier"],
            "video_jump_cycle_v28",
        )
        self.assertEqual(
            ACTION_SHEET_VARIANT["quality_tier"],
            "video_action_sheet_v28",
        )
        self.assertEqual(JUMP_CYCLE_SHEET_VARIANT["pose"], "jump-cycle-sheet")
        self.assertEqual(ACTION_SHEET_VARIANT["pose"], "action-sheet")
        self.assertEqual(
            JUMP_CYCLE_SHEET_VARIANT["motion_cells"],
            {"jumping": list(range(8))},
        )
        self.assertEqual(ACTION_SHEET_VARIANT["motion_cells"]["magic"], [4, 5])
        self.assertEqual(ACTION_SHEET_VARIANT["motion_cells"]["battle"], [6, 7])
        self.assertEqual(JUMP_CYCLE_SHEET_VARIANT["playback"], "discrete-frames")
        self.assertEqual(ACTION_SHEET_VARIANT["playback"], "discrete-frames")

        for action_name in ("battle", "interaction"):
            variant = ACTION_CYCLE_VARIANTS[action_name]
            with self.subTest(action=action_name):
                self.assertEqual(
                    variant["quality_tier"],
                    f"video_{action_name}_cycle_v28",
                )
                self.assertEqual(variant["pose"], f"{action_name}-cycle-sheet")
                self.assertEqual(
                    variant["motion_cells"],
                    {action_name: list(range(8))},
                )
                self.assertEqual(
                    variant["playback"],
                    "optical-flow-adjacent-frames",
                )

    def test_seed_prefers_v28_files_when_legacy_files_also_exist(self):
        with TemporaryDirectory() as temporary_dir:
            motion_dir = Path(temporary_dir) / "motion_sheets"
            motion_dir.mkdir()
            for filename in (
                "male_01_jump_cycle_v23.png",
                "male_01_jump_cycle_v28.png",
                "male_01_action_sheet_v23.png",
                "male_01_action_sheet_v28.png",
                "male_01_battle_cycle_v23.png",
                "male_01_battle_cycle_v28.png",
                "male_01_interaction_cycle_v23.png",
                "male_01_interaction_cycle_v28.png",
            ):
                (motion_dir / filename).touch()

            with patch.object(character_seed, "CHARACTER_ASSET_DIR", Path(temporary_dir)):
                assets = character_seed._asset_specs("male_01", [])

        selected = {
            asset["pose"]: asset
            for asset in assets
            if asset["pose"]
            in {
                "jump-cycle-sheet",
                "action-sheet",
                "battle-cycle-sheet",
                "interaction-cycle-sheet",
            }
        }
        self.assertEqual(
            selected["jump-cycle-sheet"]["filename"],
            "motion_sheets/male_01_jump_cycle_v28.png",
        )
        self.assertEqual(
            selected["action-sheet"]["quality_tier"],
            "video_action_sheet_v28",
        )
        self.assertEqual(
            selected["battle-cycle-sheet"]["quality_tier"],
            "video_battle_cycle_v28",
        )
        self.assertEqual(
            selected["interaction-cycle-sheet"]["quality_tier"],
            "video_interaction_cycle_v28",
        )

    def test_catalog_has_eight_profiles_per_gender(self):
        keys = {profile["character_key"] for profile in DEFAULT_CHARACTERS}
        self.assertEqual(len(DEFAULT_CHARACTERS), 16)
        self.assertEqual(
            keys,
            {
                *(f"male_{index:02d}" for index in range(1, 9)),
                *(f"female_{index:02d}" for index in range(1, 9)),
            },
        )
        self.assertEqual(
            sum(profile["gender"] == "male" for profile in DEFAULT_CHARACTERS),
            8,
        )
        self.assertEqual(
            sum(profile["gender"] == "female" for profile in DEFAULT_CHARACTERS),
            8,
        )

    def test_every_profile_defines_required_metadata_and_assets(self):
        for profile in DEFAULT_CHARACTERS:
            with self.subTest(character_key=profile["character_key"]):
                self.assertTrue(profile["age_group"])
                self.assertTrue(profile["role_tags"])
                self.assertTrue(profile["genres"])
                self.assertTrue(profile["description"])
                filenames = [asset["filename"] for asset in profile["assets"]]
                expected = [
                    f"{profile['character_key']}_{suffix}.png"
                    for suffix in EXPECTED_SUFFIXES
                ]
                if profile["character_key"] in PREMIUM_REFERENCE_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"{profile['character_key']}_reference_v2.png",
                    )
                    self.assertEqual(
                        profile["assets"][0]["quality_tier"],
                        "premium_reference",
                    )
                    filenames = filenames[1:]
                if profile["character_key"] in MOTION_SHEET_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"motion_sheets/{profile['character_key']}_motion_sheet_v3.png",
                    )
                    motion_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"] == "video_motion_sheet_v3"
                    )
                    self.assertEqual(motion_asset["sheet_columns"], 4)
                    self.assertEqual(motion_asset["sheet_rows"], 2)
                    self.assertEqual(motion_asset["motion_cells"]["walking"], [1, 2])
                    filenames = filenames[1:]
                if profile["character_key"] in TARGET_JOURNEY_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"motion_sheets/{profile['character_key']}_target_journey_sheet_v4.png",
                    )
                    target_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"]
                        == "video_target_journey_sheet_v4"
                    )
                    self.assertEqual(target_asset["sheet_columns"], 4)
                    self.assertEqual(target_asset["sheet_rows"], 2)
                    self.assertEqual(
                        target_asset["motion_cells"]["target_running"],
                        list(range(8)),
                    )
                    filenames = filenames[1:]
                if profile["character_key"] in RUN_CYCLE_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"motion_sheets/{profile['character_key']}_run_cycle_v16.png",
                    )
                    run_cycle_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"] == "video_run_cycle_v16"
                    )
                    self.assertEqual(run_cycle_asset["sheet_columns"], 4)
                    self.assertEqual(run_cycle_asset["sheet_rows"], 2)
                    self.assertEqual(
                        run_cycle_asset["motion_cells"]["target_running"],
                        list(range(8)),
                    )
                    self.assertEqual(
                        run_cycle_asset["playback"],
                        "discrete-frames",
                    )
                    filenames = filenames[1:]
                if profile["character_key"] in JUMP_CYCLE_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"motion_sheets/{profile['character_key']}_jump_cycle_v28.png",
                    )
                    jump_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"] == "video_jump_cycle_v28"
                    )
                    self.assertEqual(jump_asset["sheet_columns"], 4)
                    self.assertEqual(jump_asset["sheet_rows"], 2)
                    self.assertEqual(
                        jump_asset["motion_cells"]["jumping"],
                        list(range(8)),
                    )
                    filenames = filenames[1:]
                if profile["character_key"] in ACTION_SHEET_KEYS:
                    self.assertEqual(
                        filenames[0],
                        f"motion_sheets/{profile['character_key']}_action_sheet_v28.png",
                    )
                    action_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"] == "video_action_sheet_v28"
                    )
                    self.assertEqual(action_asset["sheet_columns"], 4)
                    self.assertEqual(action_asset["sheet_rows"], 2)
                    self.assertEqual(action_asset["motion_cells"]["magic"], [4, 5])
                    self.assertEqual(action_asset["motion_cells"]["battle"], [6, 7])
                    filenames = filenames[1:]
                if profile["character_key"] in ACTION_CYCLE_KEYS:
                    action_cycles = (
                        ("battle", "v28"),
                        ("magic", "v22"),
                        ("interaction", "v28"),
                        ("sit", "v2"),
                        ("stand", "v2"),
                    )
                    for action_name, version in action_cycles:
                        self.assertEqual(
                            filenames[0],
                            f"motion_sheets/{profile['character_key']}_{action_name}_cycle_{version}.png",
                        )
                        cycle_asset = next(
                            asset
                            for asset in profile["assets"]
                            if asset["quality_tier"]
                            == f"video_{action_name}_cycle_{version}"
                        )
                        self.assertEqual(
                            cycle_asset["motion_cells"][action_name],
                            list(range(8)),
                        )
                        self.assertEqual(
                            cycle_asset["playback"],
                            "optical-flow-adjacent-frames",
                        )
                        filenames = filenames[1:]
                elif profile["character_key"] in DEDICATED_ACTION_CYCLE_KEYS:
                    for action_name in ("battle", "interaction"):
                        self.assertEqual(
                            filenames[0],
                            f"motion_sheets/{profile['character_key']}_{action_name}_cycle_v28.png",
                        )
                        cycle_asset = next(
                            asset
                            for asset in profile["assets"]
                            if asset["quality_tier"]
                            == f"video_{action_name}_cycle_v28"
                        )
                        self.assertEqual(
                            cycle_asset["motion_cells"][action_name],
                            list(range(8)),
                        )
                        self.assertEqual(
                            cycle_asset["playback"],
                            "optical-flow-adjacent-frames",
                        )
                        filenames = filenames[1:]
                while filenames and filenames[0].startswith("motion_sheets/"):
                    extra_filename = filenames.pop(0)
                    match = re.search(
                        r"_(?P<action>sit|stand|crawl|climb)_cycle_(?P<version>v\d+)\.png$",
                        extra_filename,
                    )
                    self.assertIsNotNone(match, extra_filename)
                    action_name = match.group("action")
                    version = match.group("version")
                    expected_tier = f"video_{action_name}_cycle_{version}"
                    cycle_asset = next(
                        asset
                        for asset in profile["assets"]
                        if asset["quality_tier"] == expected_tier
                    )
                    self.assertEqual(
                        cycle_asset["motion_cells"][action_name],
                        list(range(8)),
                    )
                    self.assertEqual(cycle_asset["sheet_columns"], 4)
                    self.assertEqual(cycle_asset["sheet_rows"], 2)
                self.assertEqual(filenames, expected)
                self.assertTrue(
                    all(
                        asset["quality_tier"] == "fast_action"
                        for asset in profile["assets"][-len(EXPECTED_SUFFIXES):]
                    )
                )

    def test_infers_korean_gender_and_age_terms(self):
        self.assertEqual(infer_character_gender("용에게 납치된 순수한 공주 미란"), "female")
        self.assertEqual(infer_character_age_group("지혜로운 노인 나무꾼"), "elder")
        self.assertEqual(infer_character_gender("용감한 소년 용사"), "male")
        self.assertEqual(infer_character_age_group("용감한 소년 용사"), "child")
        self.assertEqual(infer_character_gender("차가운 여왕 나리"), "female")

    def test_returns_none_for_missing_or_conflicting_gender_clues(self):
        self.assertIsNone(infer_character_gender("용감한 여행자 아라"))
        self.assertIsNone(infer_character_gender("소년과 소녀의 모습을 함께 가진 수호자"))

    def test_handles_overlapping_and_conflicting_age_clues_safely(self):
        self.assertEqual(infer_character_age_group("용감한 십대 소녀"), "teen")
        self.assertEqual(infer_character_age_group("지혜로운 노인 남성"), "elder")
        self.assertIsNone(infer_character_age_group("꼬마이면서 노인인 시간의 마법사"))

    def test_cast_prefers_matching_gender_age_and_role(self):
        profiles = [_runtime_profile(profile) for profile in DEFAULT_CHARACTERS]
        cast = build_story_cast(
            {
                "target": "용에게 납치된 십대 공주 '미란'",
                "guide": "오래된 지도를 가진 노인 남자 나무꾼 '도윤'",
            },
            profiles,
            genre="royal",
        )
        by_role = {member["role"]: member for member in cast}

        self.assertEqual(by_role["target"]["gender"], "female")
        self.assertEqual(by_role["target"]["age_group"], "teen")
        self.assertIn("target", by_role["target"]["role_tags"])
        self.assertEqual(by_role["guide"]["gender"], "male")
        self.assertEqual(by_role["guide"]["age_group"], "elder")
        self.assertIn("guide", by_role["guide"]["role_tags"])


class _FakeCharacterProfilesCollection:
    def __init__(self):
        self.update_many_calls = []

    async def update_many(self, query, update):
        self.update_many_calls.append((query, update))

    async def update_one(self, *args, **kwargs):
        raise AssertionError("No profile should be upserted when test assets are empty.")


class CharacterCatalogSeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_seed_deactivates_seeded_profiles_outside_current_catalog(self):
        fake_collection = _FakeCharacterProfilesCollection()
        catalog_without_assets = [
            {**profile, "assets": []}
            for profile in DEFAULT_CHARACTERS
        ]

        with patch.object(
            character_seed,
            "character_profiles_collection",
            fake_collection,
        ), patch.object(
            character_seed,
            "DEFAULT_CHARACTERS",
            catalog_without_assets,
        ):
            seeded_count = await seed_default_character_profiles()

        self.assertEqual(seeded_count, 0)
        self.assertEqual(len(fake_collection.update_many_calls), 1)
        query, update = fake_collection.update_many_calls[0]
        self.assertEqual(query["seeded"], True)
        self.assertEqual(
            set(query["character_key"]["$nin"]),
            {profile["character_key"] for profile in DEFAULT_CHARACTERS},
        )
        self.assertEqual(update["$set"]["active"], False)
        self.assertEqual(
            update["$set"]["replaced_by_catalog"],
            "gender-balanced-v1",
        )


if __name__ == "__main__":
    unittest.main()
