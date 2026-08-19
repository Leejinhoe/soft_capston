import unittest

from character_assets import (
    build_character_action_hint,
    select_character_asset,
    select_character_motion_sheet,
    select_character_action_sheet,
    select_character_action_cycle_sheet,
    select_character_jump_cycle_sheet,
    select_character_run_cycle_sheet,
    select_character_target_journey_sheet,
)


class CharacterAssetSelectionTests(unittest.TestCase):
    def test_selects_video_motion_sheet_without_affecting_scene_asset(self):
        profile = {
            "assets": [
                {
                    "pose": "motion-sheet",
                    "quality_tier": "video_motion_sheet_v3",
                    "image_file_id": "motion-file",
                },
                {
                    "pose": "default",
                    "emotion": "neutral",
                    "image_file_id": "default-file",
                },
            ]
        }

        motion_sheet = select_character_motion_sheet(profile)
        scene_asset = select_character_asset(profile, "A quiet story scene")

        self.assertEqual(motion_sheet["image_file_id"], "motion-file")
        self.assertEqual(scene_asset["image_file_id"], "default-file")

    def test_selects_target_journey_sheet_separately(self):
        profile = {
            "assets": [
                {
                    "pose": "motion-sheet",
                    "quality_tier": "video_motion_sheet_v3",
                    "image_file_id": "front-motion-file",
                },
                {
                    "pose": "target-journey-sheet",
                    "quality_tier": "video_target_journey_sheet_v4",
                    "image_file_id": "rear-motion-file",
                },
            ]
        }

        self.assertEqual(
            select_character_motion_sheet(profile)["image_file_id"],
            "front-motion-file",
        )
        self.assertEqual(
            select_character_target_journey_sheet(profile)["image_file_id"],
            "rear-motion-file",
        )

    def test_selects_run_cycle_sheet_separately(self):
        profile = {
            "assets": [
                {
                    "pose": "target-journey-sheet",
                    "quality_tier": "video_target_journey_sheet_v4",
                    "image_file_id": "rear-motion-file",
                },
                {
                    "pose": "run-cycle-sheet",
                    "quality_tier": "video_run_cycle_v16",
                    "image_file_id": "run-cycle-file",
                },
            ]
        }

        self.assertEqual(
            select_character_run_cycle_sheet(profile)["image_file_id"],
            "run-cycle-file",
        )

    def test_selects_jump_cycle_sheet_separately(self):
        profile = {
            "assets": [
                {
                    "pose": "motion-sheet",
                    "quality_tier": "video_motion_sheet_v3",
                    "image_file_id": "motion-file",
                },
                {
                    "pose": "jump-cycle-sheet",
                    "quality_tier": "video_jump_cycle_v20",
                    "image_file_id": "legacy-jump-cycle-file",
                },
                {
                    "pose": "jump-cycle-sheet",
                    "quality_tier": "video_jump_cycle_v23",
                    "image_file_id": "legacy-jump-cycle-v23-file",
                },
                {
                    "pose": "jump-cycle-sheet",
                    "quality_tier": "video_jump_cycle_v28",
                    "image_file_id": "jump-cycle-file",
                },
            ]
        }

        self.assertEqual(
            select_character_jump_cycle_sheet(profile)["image_file_id"],
            "jump-cycle-file",
        )

    def test_selects_action_sheet_separately(self):
        profile = {
            "assets": [
                {
                    "pose": "action-sheet",
                    "quality_tier": "video_action_sheet_v21",
                    "image_file_id": "legacy-action-sheet-file",
                },
                {
                    "pose": "action-sheet",
                    "quality_tier": "video_action_sheet_v23",
                    "image_file_id": "legacy-action-sheet-v23-file",
                },
                {
                    "pose": "action-sheet",
                    "quality_tier": "video_action_sheet_v28",
                    "image_file_id": "action-sheet-file",
                },
            ]
        }

        self.assertEqual(
            select_character_action_sheet(profile)["image_file_id"],
            "action-sheet-file",
        )
        self.assertIsNone(select_character_asset(profile, "battle"))

    def test_selects_dedicated_action_cycle_and_excludes_it_from_scene_assets(self):
        profile = {
            "assets": [
                {
                    "pose": "battle-cycle-sheet",
                    "quality_tier": "video_battle_cycle_v22",
                    "image_file_id": "legacy-battle-cycle-file",
                },
                {
                    "pose": "battle-cycle-sheet",
                    "quality_tier": "video_battle_cycle_v23",
                    "image_file_id": "legacy-battle-cycle-v23-file",
                },
                {
                    "pose": "battle-cycle-sheet",
                    "quality_tier": "video_battle_cycle_v28",
                    "image_file_id": "battle-cycle-file",
                },
                {
                    "pose": "default",
                    "quality_tier": "fast_action",
                    "image_file_id": "default-file",
                },
            ]
        }

        self.assertEqual(
            select_character_action_cycle_sheet(profile, "battle")["image_file_id"],
            "battle-cycle-file",
        )
        self.assertEqual(
            select_character_asset(profile, "battle")["image_file_id"],
            "default-file",
        )

    def test_legacy_versions_are_ordered_fallbacks(self):
        profile = {
            "assets": [
                {"pose": "jump-cycle-sheet", "quality_tier": "video_jump_cycle_v20", "image_file_id": "jump-v20"},
                {"pose": "jump-cycle-sheet", "quality_tier": "video_jump_cycle_v23", "image_file_id": "jump-v23"},
                {"pose": "action-sheet", "quality_tier": "video_action_sheet_v21", "image_file_id": "action-v21"},
                {"pose": "action-sheet", "quality_tier": "video_action_sheet_v23", "image_file_id": "action-v23"},
                {"pose": "battle-cycle-sheet", "quality_tier": "video_battle_cycle_v22", "image_file_id": "battle-v22"},
                {"pose": "battle-cycle-sheet", "quality_tier": "video_battle_cycle_v23", "image_file_id": "battle-v23"},
                {"pose": "interaction-cycle-sheet", "quality_tier": "video_interaction_cycle_v22", "image_file_id": "interaction-v22"},
                {"pose": "interaction-cycle-sheet", "quality_tier": "video_interaction_cycle_v23", "image_file_id": "interaction-v23"},
            ]
        }

        self.assertEqual(
            select_character_jump_cycle_sheet(profile)["image_file_id"],
            "jump-v23",
        )
        self.assertEqual(
            select_character_action_sheet(profile)["image_file_id"],
            "action-v23",
        )
        self.assertEqual(
            select_character_action_cycle_sheet(profile, "battle")["image_file_id"],
            "battle-v23",
        )
        self.assertEqual(
            select_character_action_cycle_sheet(profile, "interaction")["image_file_id"],
            "interaction-v23",
        )

    def test_selects_sit_and_stand_cycles_as_video_assets(self):
        profile = {
            "assets": [
                {
                    "pose": "sit-cycle-sheet",
                    "quality_tier": "video_sit_cycle_v1",
                    "image_file_id": "sit-cycle-file",
                },
                {
                    "pose": "stand-cycle-sheet",
                    "quality_tier": "video_stand_cycle_v1",
                    "image_file_id": "stand-cycle-file",
                },
                {
                    "pose": "default",
                    "quality_tier": "fast_action",
                    "image_file_id": "default-file",
                },
            ]
        }

        self.assertEqual(
            select_character_action_cycle_sheet(profile, "sit")["image_file_id"],
            "sit-cycle-file",
        )
        self.assertEqual(
            select_character_action_cycle_sheet(profile, "stand")["image_file_id"],
            "stand-cycle-file",
        )
        self.assertEqual(
            select_character_asset(profile, "The hero sits down")["image_file_id"],
            "default-file",
        )

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

    def test_quality_mode_keeps_premium_identity_for_action_scene(self):
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
            prefer_premium_reference=True,
        )

        self.assertEqual(selected["image_file_id"], "premium-file")

    def test_video_sheet_is_never_used_as_a_scene_character(self):
        self.profile["assets"].insert(
            0,
            {
                "pose": "target-journey-sheet",
                "quality_tier": "video_target_journey_sheet_v4",
                "image_file_id": "journey-sheet-file",
                "scene_keywords": ["castle"],
            },
        )

        selected = select_character_asset(
            self.profile,
            "The hero runs toward the castle.",
        )

        self.assertNotEqual(selected["image_file_id"], "journey-sheet-file")

    def test_prefers_requested_action_pose_when_story_words_are_ambiguous(self):
        self.profile["assets"].append(
            {
                "pose": "walking",
                "emotion": "determined",
                "image_file_id": "walking-file",
                "scene_keywords": [],
            }
        )

        selected = select_character_asset(
            self.profile,
            "A new scene begins.",
            preferred_pose="walking",
            preferred_emotion="determined",
        )

        self.assertEqual(selected["image_file_id"], "walking-file")

    def test_action_hint_includes_learned_partner_prop_and_body_focus(self):
        hint = build_character_action_hint(
            self.profile["assets"][0],
            visual_context={
                "action_semantics": {
                    "interaction_kind": "handoff_receive",
                    "requires_partner": True,
                    "subject_role": "receiver",
                    "partner_role": "giver",
                    "requires_object": True,
                    "object_role": "transferred_item",
                    "body_focus": "hands",
                }
            },
        )

        self.assertIn("handoff receive", hint)
        self.assertIn("receiver visibly interacting with giver", hint)
        self.assertIn("clearly visible transferred item", hint)
        self.assertIn("readable hands action", hint)


if __name__ == "__main__":
    unittest.main()
