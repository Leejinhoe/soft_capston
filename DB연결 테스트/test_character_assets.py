import unittest

from character_assets import (
    build_character_action_hint,
    detect_character_action_group,
    detect_character_action_groups,
    select_character_action_cycle,
    select_character_action_cycles,
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

    def test_detects_new_run_jump_and_magic_actions(self):
        self.assertEqual(
            detect_character_action_group("The hero runs across the bridge."),
            "run",
        )
        self.assertEqual(
            detect_character_action_group(
                "\uc6a9\uc0ac\uac00 \ub192\uc774 \uc810\ud504\ud588\ub2e4."
            ),
            "jump",
        )
        self.assertEqual(
            detect_character_action_group(
                "\uc6a9\uc0ac\uac00 \ub9c8\ubc95 \uc8fc\ubb38\uc744 \uc678\uc6e0\ub2e4."
            ),
            "magic",
        )

    def test_castle_does_not_trigger_magic_casting(self):
        self.assertEqual(
            detect_character_action_group("The hero walks toward the castle."),
            "walk",
        )

    def test_detects_multiple_actions_in_story_order(self):
        actions = detect_character_action_groups(
            "The hero walks to the gate, jumps over a rock, then casts magic."
        )

        self.assertEqual(actions, ["walk", "jump", "magic"])

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
                    "animation_version": 1,
                },
                {
                    "quality_tier": "premium_action_cycle",
                    "animation_group": "fight",
                    "image_file_id": "fight-cycle-v2",
                    "animation_version": 2,
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
        self.assertEqual(fighting["image_file_id"], "fight-cycle-v2")

    def test_selects_ordered_action_cycle_sequence(self):
        profile = {
            "assets": [
                {
                    "quality_tier": "premium_action_cycle",
                    "animation_group": action,
                    "image_file_id": f"{action}-cycle",
                }
                for action in ("walk", "jump", "magic")
            ]
        }

        selected = select_character_action_cycles(
            profile,
            "The hero walks, jumps, and casts magic.",
        )

        self.assertEqual(
            [asset["animation_group"] for asset in selected],
            ["walk", "jump", "magic"],
        )


if __name__ == "__main__":
    unittest.main()
