import unittest
from unittest.mock import patch

import character_seed
from character_seed import DEFAULT_CHARACTERS, seed_default_character_profiles
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
                action_cycles = [
                    asset
                    for asset in profile["assets"]
                    if asset["quality_tier"] == "premium_action_cycle"
                ]
                if profile["character_key"] == "male_01":
                    self.assertEqual(
                        {asset["animation_group"] for asset in action_cycles},
                        {"walk", "fight", "run", "jump", "magic"},
                    )
                    preferred_fight = max(
                        (
                            asset
                            for asset in action_cycles
                            if asset["animation_group"] == "fight"
                        ),
                        key=lambda asset: asset["animation_version"],
                    )
                    self.assertEqual(preferred_fight["animation_version"], 2)
                    self.assertEqual(preferred_fight["animation_frame_count"], 6)
                    self.assertEqual(preferred_fight["animation_layout"], "3x2")
                else:
                    self.assertEqual(action_cycles, [])
                fast_action_filenames = [
                    asset["filename"]
                    for asset in profile["assets"]
                    if asset["quality_tier"] == "fast_action"
                ]
                self.assertEqual(fast_action_filenames, expected)
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
