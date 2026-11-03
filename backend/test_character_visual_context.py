import unittest

from character_assets import build_character_action_hint, select_character_asset


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

    def test_prompt_hint_includes_learned_prop_emotion_and_motion_style(self):
        hint = build_character_action_hint(
            None,
            visual_context={
                "prop_tags": ["woven_basket"],
                "emotion_tags": ["happy"],
                "motion_modifier_tags": ["slow_subtle"],
            },
        )

        self.assertIn("clearly visible woven basket", hint)
        self.assertIn("happy expression", hint)
        self.assertIn("slow subtle motion", hint)

    def test_story_emotion_overrides_automatic_journey_emotion(self):
        profile = {
            "assets": [
                {
                    "pose": "default",
                    "emotion": "happy",
                    "image_file_id": "happy-file",
                    "scene_keywords": [],
                },
                {
                    "pose": "walking",
                    "emotion": "determined",
                    "image_file_id": "walking-file",
                    "scene_keywords": [],
                },
            ]
        }

        selected = select_character_asset(
            profile,
            "아이는 슬며시 걸으며 방긋 웃었다.",
            visual_context={"emotion_tags": ["happy"]},
            preferred_pose="walking",
            preferred_emotion="determined",
        )

        self.assertEqual(selected["image_file_id"], "happy-file")


if __name__ == "__main__":
    unittest.main()
