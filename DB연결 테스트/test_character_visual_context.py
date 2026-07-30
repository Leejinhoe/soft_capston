import unittest

from character_assets import select_character_asset


class CharacterVisualContextTests(unittest.TestCase):
    def test_visual_action_selects_matching_pose(self):
        profile = {
            "assets": [
                {
                    "pose": "default",
                    "emotion": "neutral",
                    "image_file_id": "default-file",
                    "scene_keywords": [],
                },
                {
                    "pose": "investigating",
                    "emotion": "curious",
                    "image_file_id": "action-file",
                    "scene_keywords": [],
                },
            ]
        }

        selected = select_character_asset(
            profile,
            "주인공은 조용히 방을 둘러보았다.",
            visual_context={
                "action_tags": ["investigating"],
                "emotion_tags": ["curious"],
            },
        )

        self.assertEqual(selected["image_file_id"], "action-file")


if __name__ == "__main__":
    unittest.main()
