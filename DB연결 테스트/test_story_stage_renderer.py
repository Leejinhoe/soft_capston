import unittest

from PIL import Image, ImageDraw, ImageFilter

import story_stage_renderer


class StoryStageRendererTests(unittest.TestCase):
    def test_stage_requires_approach_jump_and_magic(self):
        self.assertTrue(
            story_stage_renderer.supports_story_stage(
                ["walk", "jump", "magic"]
            )
        )
        self.assertFalse(
            story_stage_renderer.supports_story_stage(["walk", "magic"])
        )
        self.assertFalse(
            story_stage_renderer.supports_story_stage(
                ["walk", "jump", "magic"],
                "The child happily jumps and creates a rainbow.",
            )
        )
        self.assertTrue(
            story_stage_renderer.supports_story_stage(
                ["walk", "jump", "magic"],
                "The enchanted roots blocked the road.",
            )
        )
        self.assertTrue(
            story_stage_renderer.supports_story_stage(
                ["walk", "jump", "magic"],
                "\ub9c8\ubc95 \ubfcc\ub9ac\uac00 \uae38\uc744 "
                "\ub9c9\uace0 \ubd09\uc778\uc774 \ube5b\ub0ac\ub2e4.",
            )
        )

    def test_stage_places_obstacle_and_target_inside_frame(self):
        stage = story_stage_renderer.prepare_story_stage(
            ["walk", "jump", "magic"],
            Image,
            width=512,
            height=384,
        )

        self.assertIsNotNone(stage)
        self.assertEqual(stage["id"], story_stage_renderer.STAGE_ID)
        self.assertGreater(stage["prop"].width, 100)
        self.assertLess(stage["target"][0], 512)
        self.assertLess(stage["target"][1], 384)
        self.assertLess(stage["target"][1], stage["position"][1])
        self.assertLess(stage["destination"][1], stage["target"][1])
        self.assertGreater(stage["destination"][0], stage["target"][0])

    def test_seal_brightens_when_hero_reaches_obstacle(self):
        approaching = story_stage_renderer.story_stage_state("walk", 0.5)
        noticed = story_stage_renderer.story_stage_state("walk", 0.95)

        self.assertGreater(noticed["seal_glow"], approaching["seal_glow"])

    def test_magic_unlock_state_fades_obstacle_after_impact(self):
        before = story_stage_renderer.story_stage_state("magic", 0.2)
        after = story_stage_renderer.story_stage_state("magic", 0.95)

        self.assertEqual(before["prop_opacity"], 1.0)
        self.assertEqual(after["prop_opacity"], 0.0)
        self.assertGreater(after["success_strength"], 0.9)

    def test_story_stage_changes_background_pixels(self):
        stage = story_stage_renderer.prepare_story_stage(
            ["walk", "jump", "magic"],
            Image,
            width=512,
            height=384,
        )
        background = Image.new("RGBA", (512, 384), (70, 120, 180, 255))
        staged = story_stage_renderer.compose_story_stage_background(
            background,
            stage,
            action_name="jump",
            action_progress=0.5,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
        )

        self.assertNotEqual(background.tobytes(), staged.tobytes())

    def test_magic_beam_changes_foreground_near_target(self):
        stage = story_stage_renderer.prepare_story_stage(
            ["walk", "jump", "magic"],
            Image,
            width=512,
            height=384,
        )
        frame = Image.new("RGBA", (512, 384), (70, 120, 180, 255))
        effected = story_stage_renderer.composite_story_action_effects(
            frame.copy(),
            stage,
            action_name="magic",
            action_progress=0.58,
            character_box=(300, 100, 120, 240),
            feet_center=(360, 340),
            camera_progress=0.8,
            motion_strength=4,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
        )

        self.assertNotEqual(frame.tobytes(), effected.tobytes())


if __name__ == "__main__":
    unittest.main()
