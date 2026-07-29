import unittest

from character_assets import build_character_action_hint, select_character_asset


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


if __name__ == "__main__":
    unittest.main()
