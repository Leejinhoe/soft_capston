import unittest

from character_assets import (
    build_character_action_hint,
    detect_character_action_group,
    select_character_action_cycle,
    select_character_asset,
    select_premium_reference_asset,
)


class CharacterAssetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "assets": [
                {
                    "pose": "default",
                    "emotion": "neutral",
                    "image_file_id": "default-file",
                    "scene_keywords": [],
                },
                {
                    "pose": "walking",
                    "emotion": "determined",
                    "image_file_id": "walking-file",
                    "scene_keywords": ["walk"],
                },
                {
                    "pose": "casting-magic",
                    "emotion": "joyful",
                    "image_file_id": "magic-file",
                    "scene_keywords": ["magic", "마법", "주문"],
                },
            ]
        }

    def test_selects_action_asset_from_scene_keyword(self):
        selected = select_character_asset(
            self.profile,
            "미나는 반짝이는 마법 주문을 외웠다.",
        )

        self.assertEqual(selected["image_file_id"], "magic-file")
        self.assertEqual(
            build_character_action_hint(selected),
            "casting-magic pose, joyful expression",
        )

    def test_falls_back_to_default_asset(self):
        selected = select_character_asset(
            self.profile,
            "미나는 창밖의 달을 조용히 바라보았다.",
        )

        self.assertEqual(selected["image_file_id"], "default-file")

    def test_prefers_first_premium_reference_for_neutral_scene(self):
        self.profile["assets"].insert(
            0,
            {
                "pose": "default",
                "emotion": "neutral",
                "quality_tier": "premium_reference",
                "image_file_id": "premium-file",
                "scene_keywords": [],
            },
        )

        selected = select_character_asset(
            self.profile,
            "A quiet moment before the journey begins.",
        )

        self.assertEqual(selected["image_file_id"], "premium-file")

    def test_action_asset_still_beats_premium_reference(self):
        self.profile["assets"].insert(
            0,
            {
                "pose": "default",
                "emotion": "neutral",
                "quality_tier": "premium_reference",
                "image_file_id": "premium-file",
                "scene_keywords": [],
            },
        )

        selected = select_character_asset(
            self.profile,
            "The hero begins to cast magic.",
        )

        self.assertEqual(selected["image_file_id"], "magic-file")

    def test_primary_movement_beats_decorative_magic_keyword(self):
        selected = select_character_asset(
            self.profile,
            "The hero runs quickly toward the magic door.",
        )

        self.assertEqual(selected["image_file_id"], "walking-file")

    def test_video_reference_selection_uses_premium_profile_asset(self):
        self.profile["assets"].insert(
            0,
            {
                "pose": "default",
                "emotion": "neutral",
                "quality_tier": "premium_reference",
                "image_file_id": "premium-file",
                "scene_keywords": [],
            },
        )

        selected = select_premium_reference_asset(self.profile)

        self.assertEqual(selected["image_file_id"], "premium-file")

    def test_detects_korean_walk_and_fight_actions(self):
        self.assertEqual(
            detect_character_action_group(
                "\uc6a9\uc0ac\ub294 \uc131\uc744 \ud5a5\ud574 \uac78\uc5b4\uac14\ub2e4."
            ),
            "walk",
        )
        self.assertEqual(
            detect_character_action_group(
                "\uc6a9\uc0ac\ub294 \uac80\uc744 \ub4e4\uace0 \uc801\uacfc \uc2f8\uc6b0\uae30 \uc2dc\uc791\ud588\ub2e4."
            ),
            "fight",
        )

    def test_selects_matching_premium_action_cycle(self):
        profile = {
            "assets": [
                {
                    "quality_tier": "premium_action_cycle",
                    "animation_group": "walk",
                    "image_file_id": "walk-cycle",
                },
                {
                    "quality_tier": "premium_action_cycle",
                    "animation_group": "fight",
                    "image_file_id": "fight-cycle",
                },
            ]
        }

        walking = select_character_action_cycle(
            profile,
            "The hero walks toward the castle.",
        )
        fighting = select_character_action_cycle(
            profile,
            "The hero blocks an attack with his sword.",
        )

        self.assertEqual(walking["image_file_id"], "walk-cycle")
        self.assertEqual(fighting["image_file_id"], "fight-cycle")


if __name__ == "__main__":
    unittest.main()
