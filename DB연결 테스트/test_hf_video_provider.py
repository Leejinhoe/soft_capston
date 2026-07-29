import unittest

from PIL import Image, ImageEnhance, ImageOps

import hf_video_provider


class LocalCharacterVideoTests(unittest.TestCase):
    def test_motion_preset_uses_story_action_keywords(self):
        self.assertEqual(
            hf_video_provider.select_motion_preset("용사가 숲길을 빠르게 달리기 시작했다."),
            "run",
        )
        self.assertEqual(
            hf_video_provider.select_motion_preset("The fairy flies over the castle."),
            "fly",
        )
        self.assertEqual(
            hf_video_provider.select_motion_preset("친구에게 손을 흔들며 인사했다."),
            "wave",
        )
        self.assertEqual(
            hf_video_provider.select_motion_preset("A quiet portrait in the library."),
            "idle",
        )

    def test_layered_character_frame_changes_character_position(self):
        background = Image.new("RGBA", (320, 256), (70, 120, 180, 255))
        character = Image.new("RGBA", (80, 150), (0, 0, 0, 0))
        for x in range(15, 65):
            for y in range(8, 145):
                character.putpixel((x, y), (220, 70, 90, 255))

        start = hf_video_provider._render_layered_frame(
            background=background,
            character=character,
            position=(120, 90),
            Image=Image,
            ImageEnhance=ImageEnhance,
            ImageOps=ImageOps,
            width=320,
            height=256,
            progress=0.0,
            motion_strength=8,
            motion_preset="run",
        )
        moving = hf_video_provider._render_layered_frame(
            background=background,
            character=character,
            position=(120, 90),
            Image=Image,
            ImageEnhance=ImageEnhance,
            ImageOps=ImageOps,
            width=320,
            height=256,
            progress=0.25,
            motion_strength=8,
            motion_preset="run",
        )

        self.assertEqual(start.size, (320, 256))
        self.assertEqual(moving.size, (320, 256))
        self.assertNotEqual(start.tobytes(), moving.tobytes())

    def test_jump_motion_lifts_character_and_reduces_shadow(self):
        grounded = hf_video_provider._character_motion(
            preset="jump",
            progress=0.0,
            width=512,
            height=384,
            motion_strength=8,
        )
        airborne = hf_video_provider._character_motion(
            preset="jump",
            progress=0.5,
            width=512,
            height=384,
            motion_strength=8,
        )

        self.assertLess(airborne["y"], grounded["y"])
        self.assertLess(airborne["shadow_scale"], grounded["shadow_scale"])
        self.assertLess(airborne["shadow_opacity"], grounded["shadow_opacity"])

    def test_video_length_is_capped_at_fifteen_seconds(self):
        frame_rate = 12
        frames = hf_video_provider._normalize_frame_count(999, frame_rate)

        self.assertEqual(frames, 15 * frame_rate)

    def test_run_motion_keeps_character_near_center(self):
        motion = hf_video_provider._character_motion(
            preset="run",
            progress=0.25,
            width=512,
            height=384,
            motion_strength=8,
            elapsed_seconds=0.25,
        )

        self.assertLessEqual(abs(motion["x"]), 2)
        self.assertLessEqual(abs(motion["angle"]), 0.5)

    def test_gait_alternation_keeps_upper_body_unchanged(self):
        character = Image.new("RGBA", (40, 100), (0, 0, 0, 0))
        for x in range(4, 18):
            for y in range(5, 60):
                character.putpixel((x, y), (220, 60, 80, 255))
        for x in range(4, 14):
            for y in range(75, 98):
                character.putpixel((x, y), (40, 80, 220, 255))

        alternate = hf_video_provider._alternate_lower_body_pose(
            character,
            Image,
            ImageOps,
        )

        split_y = round(character.height * 0.68)
        self.assertEqual(
            character.crop((0, 0, character.width, split_y)).tobytes(),
            alternate.crop((0, 0, alternate.width, split_y)).tobytes(),
        )
        self.assertNotEqual(
            character.crop((0, split_y, character.width, character.height)).tobytes(),
            alternate.crop((0, split_y, alternate.width, alternate.height)).tobytes(),
        )


if __name__ == "__main__":
    unittest.main()
