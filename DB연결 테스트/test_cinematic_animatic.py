import unittest

from PIL import Image, ImageDraw, ImageFilter

import cinematic_animatic


class CinematicAnimaticTests(unittest.TestCase):
    def setUp(self):
        self.frame_counts = {"walk": 2, "jump": 6, "magic": 6}

    def test_story_action_sequence_enables_cinematic_mode(self):
        self.assertTrue(
            cinematic_animatic.supports_cinematic_animatic(
                ["walk", "jump", "magic"],
                True,
            )
        )
        self.assertFalse(
            cinematic_animatic.supports_cinematic_animatic(
                ["walk", "magic"],
                True,
            )
        )
        self.assertFalse(
            cinematic_animatic.supports_cinematic_animatic(
                ["walk", "jump", "magic"],
                False,
            )
        )

    def test_timeline_contains_readable_story_beats_in_order(self):
        shot_ids = []
        for frame_index in range(216):
            state = cinematic_animatic.resolve_cinematic_shot(
                frame_index,
                216,
                24,
                self.frame_counts,
            )
            if not shot_ids or shot_ids[-1] != state["shot_id"]:
                shot_ids.append(state["shot_id"])

        self.assertEqual(
            shot_ids,
            [
                "approach",
                "notice",
                "crouch",
                "takeoff",
                "flight",
                "apex",
                "landing",
                "recovery",
                "charge",
                "release",
                "resolution",
            ],
        )

    def test_each_frame_selects_a_clean_existing_pose(self):
        for frame_index in range(216):
            state = cinematic_animatic.resolve_cinematic_shot(
                frame_index,
                216,
                24,
                self.frame_counts,
            )
            frame_count = self.frame_counts[state["action_name"]]
            self.assertIsInstance(state["pose_index"], int)
            self.assertGreaterEqual(state["pose_index"], 0)
            self.assertLess(state["pose_index"], frame_count)
            self.assertGreaterEqual(state["cut_strength"], 0.0)
            self.assertLessEqual(state["cut_strength"], 1.0)

    def test_jump_has_takeoff_apex_and_grounded_landing(self):
        states = [
            cinematic_animatic.resolve_cinematic_shot(
                frame_index,
                216,
                24,
                self.frame_counts,
            )
            for frame_index in range(216)
        ]
        takeoff = next(state for state in states if state["shot_id"] == "takeoff")
        apex = next(state for state in states if state["shot_id"] == "apex")
        landing = [
            state for state in states if state["shot_id"] == "landing"
        ][-1]

        self.assertLess(apex["y_ratio"], takeoff["y_ratio"])
        self.assertLess(apex["y_ratio"], landing["y_ratio"])
        self.assertAlmostEqual(landing["y_ratio"], 0.0, delta=0.02)
        self.assertGreater(landing["x_ratio"], takeoff["x_ratio"])

    def test_cut_effect_preserves_frame_dimensions(self):
        frame = Image.new("RGB", (320, 240), (40, 60, 80))
        state = cinematic_animatic.resolve_cinematic_shot(
            0,
            216,
            24,
            self.frame_counts,
        )
        state["cut_strength"] = 1.0

        result = cinematic_animatic.apply_cinematic_cut_effect(
            frame,
            state,
            Image,
            ImageDraw,
            ImageFilter,
        )

        self.assertEqual(result.size, frame.size)
        self.assertEqual(result.mode, "RGB")

    def test_short_timelines_still_return_valid_states(self):
        for frame_index in range(6):
            state = cinematic_animatic.resolve_cinematic_shot(
                frame_index,
                6,
                6,
                self.frame_counts,
            )
            self.assertIn(state["action_name"], self.frame_counts)
            self.assertTrue(state["shot_id"])


if __name__ == "__main__":
    unittest.main()
