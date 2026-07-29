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


if __name__ == "__main__":
    unittest.main()
