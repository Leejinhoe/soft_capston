import io
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
        self.assertEqual(
            hf_video_provider.select_motion_preset(
                "The hero walks toward the castle."
            ),
            "walk",
        )
        self.assertEqual(
            hf_video_provider.select_motion_preset(
                "\uc6a9\uc0ac\uac00 \uac80\uc744 \ub4e4\uace0 \uc2f8\uc6b0\uae30 \uc2dc\uc791\ud588\ub2e4."
            ),
            "fight",
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

    def test_quality_steps_increase_internal_render_scale(self):
        self.assertEqual(hf_video_provider._quality_render_scale(0), 1.0)
        self.assertEqual(hf_video_provider._quality_render_scale(8), 1.2)
        self.assertEqual(hf_video_provider._quality_render_scale(12), 1.3)
        self.assertEqual(hf_video_provider._quality_render_scale(50), 1.5)

    def test_run_motion_keeps_character_near_center(self):
        motion = hf_video_provider._character_motion(
            preset="run",
            progress=0.25,
            width=512,
            height=384,
            motion_strength=8,
            elapsed_seconds=0.25,
        )

        self.assertGreater(abs(motion["x"]), 1)
        self.assertLessEqual(abs(motion["x"]), 4)
        self.assertGreater(abs(motion["angle"]), 0.2)
        self.assertLessEqual(abs(motion["angle"]), 1.0)

    def test_walk_render_does_not_mutate_or_split_character_source(self):
        character = Image.new("RGBA", (40, 100), (0, 0, 0, 0))
        for x in range(4, 18):
            for y in range(5, 60):
                character.putpixel((x, y), (220, 60, 80, 255))
        for x in range(4, 14):
            for y in range(75, 98):
                character.putpixel((x, y), (40, 80, 220, 255))
        original = character.tobytes()
        background = Image.new("RGBA", (320, 256), (70, 120, 180, 255))

        frame = hf_video_provider._render_layered_frame(
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
            motion_preset="walk",
        )

        self.assertEqual(character.tobytes(), original)
        self.assertEqual(frame.size, (320, 256))

    def test_action_sheet_is_split_and_normalized_as_four_frames(self):
        sheet = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        colors = (
            (230, 40, 40, 255),
            (40, 230, 40, 255),
            (40, 40, 230, 255),
            (230, 180, 40, 255),
        )
        for index, color in enumerate(colors):
            x = (index % 2) * 40
            y = (index // 2) * 40
            for px in range(x + 8, x + 32):
                for py in range(y + 5, y + 36):
                    sheet.putpixel((px, py), color)
        buffer = io.BytesIO()
        sheet.save(buffer, format="PNG")

        frames, position = hf_video_provider._prepare_action_cycle_frames(
            buffer.getvalue(),
            Image,
            width=320,
            height=256,
            layout="2x2",
            frame_count=4,
        )

        self.assertEqual(len(frames), 4)
        self.assertIsNotNone(position)
        self.assertEqual({frame.size for frame in frames}, {frames[0].size})
        self.assertTrue(all(frame.getchannel("A").getbbox() for frame in frames))

    def test_three_by_two_action_sheet_is_split_as_six_frames(self):
        sheet = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
        for index in range(6):
            x = (index % 3) * 40
            y = (index // 3) * 40
            for px in range(x + 7, x + 33):
                for py in range(y + 4, y + 37):
                    sheet.putpixel((px, py), (30 * index, 100, 220, 255))
        buffer = io.BytesIO()
        sheet.save(buffer, format="PNG")

        frames, position = hf_video_provider._prepare_action_cycle_frames(
            buffer.getvalue(),
            Image,
            width=320,
            height=256,
            layout="3x2",
            frame_count=6,
        )

        self.assertEqual(len(frames), 6)
        self.assertIsNotNone(position)
        self.assertEqual({frame.size for frame in frames}, {frames[0].size})

    def test_action_sheet_preserves_relative_pose_scale(self):
        sheet = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
        for px in range(8, 32):
            for py in range(18, 36):
                sheet.putpixel((px, py), (230, 60, 80, 255))
        for px in range(48, 72):
            for py in range(4, 36):
                sheet.putpixel((px, py), (60, 120, 230, 255))
        buffer = io.BytesIO()
        sheet.save(buffer, format="PNG")

        frames, _ = hf_video_provider._prepare_action_cycle_frames(
            buffer.getvalue(),
            Image,
            width=320,
            height=256,
            layout="2x1",
            frame_count=2,
        )
        visible_heights = [
            frame.getchannel("A").getbbox()[3] - frame.getchannel("A").getbbox()[1]
            for frame in frames
        ]

        self.assertGreater(visible_heights[1], visible_heights[0] * 1.5)

    def test_action_cycle_index_advances_by_action_timing(self):
        walk_indexes = [
            hf_video_provider._action_cycle_frame_index("walk", time, 4)
            for time in (0.0, 0.2, 0.4, 0.6)
        ]
        fight_indexes = [
            hf_video_provider._action_cycle_frame_index("fight", time, 4)
            for time in (0.0, 0.4, 0.8, 1.2)
        ]

        self.assertGreater(len(set(walk_indexes)), 1)
        self.assertGreater(len(set(fight_indexes)), 1)

    def test_walk_action_cycle_travels_across_the_scene(self):
        start = hf_video_provider._action_cycle_motion(
            "walk",
            elapsed_seconds=0.0,
            progress=0.0,
            width=512,
            height=384,
            frame_index=0,
        )
        end = hf_video_provider._action_cycle_motion(
            "walk",
            elapsed_seconds=6.0,
            progress=1.0,
            width=512,
            height=384,
            frame_index=0,
        )

        self.assertLess(start["x"], 0)
        self.assertGreater(end["x"], 0)
        self.assertGreater(end["x"] - start["x"], 200)

    def test_fight_action_cycle_lunges_and_returns_to_guard(self):
        guard = hf_video_provider._action_cycle_motion(
            "fight",
            elapsed_seconds=0.0,
            progress=0.0,
            width=512,
            height=384,
            frame_index=3,
        )
        lunge = hf_video_provider._action_cycle_motion(
            "fight",
            elapsed_seconds=1.6,
            progress=0.5,
            width=512,
            height=384,
            frame_index=2,
        )
        recovered = hf_video_provider._action_cycle_motion(
            "fight",
            elapsed_seconds=2.99,
            progress=1.0,
            width=512,
            height=384,
            frame_index=3,
        )

        self.assertGreater(lunge["x"], guard["x"] + 30)
        self.assertAlmostEqual(recovered["x"], guard["x"], delta=1.0)

    def test_jump_action_has_clear_airborne_apex(self):
        grounded = hf_video_provider._action_cycle_motion(
            "jump",
            elapsed_seconds=0.0,
            progress=0.0,
            width=512,
            height=384,
            frame_index=0,
            cycle_progress=0.0,
        )
        apex = hf_video_provider._action_cycle_motion(
            "jump",
            elapsed_seconds=1.2,
            progress=0.5,
            width=512,
            height=384,
            frame_index=3,
            cycle_progress=0.55,
        )

        self.assertLess(apex["y"], grounded["y"] - 80)
        self.assertLess(apex["shadow_scale"], grounded["shadow_scale"])
        self.assertLess(apex["shadow_opacity"], grounded["shadow_opacity"])

    def test_jump_cycle_returns_to_ready_pose_before_next_action(self):
        recovered_index = hf_video_provider._action_cycle_frame_index(
            "jump",
            elapsed_seconds=2.35,
            frame_count=6,
            cycle_seconds=2.4,
            cycle_progress=0.95,
        )

        self.assertEqual(recovered_index, 0)

    def test_magic_action_builds_and_releases_energy_without_root_slide(self):
        ready = hf_video_provider._action_cycle_motion(
            "magic",
            elapsed_seconds=0.0,
            progress=0.0,
            width=512,
            height=384,
            frame_index=0,
            cycle_progress=0.0,
        )
        casting = hf_video_provider._action_cycle_motion(
            "magic",
            elapsed_seconds=1.5,
            progress=0.5,
            width=512,
            height=384,
            frame_index=3,
            cycle_progress=0.5,
        )

        self.assertEqual(ready["x"], 0)
        self.assertEqual(casting["x"], 0)
        self.assertGreater(casting["scale_x"], ready["scale_x"])

    def test_action_sequence_root_positions_connect_at_center(self):
        walk_bounds = hf_video_provider._action_travel_bounds("walk", 0, 2)
        fight_bounds = hf_video_provider._action_travel_bounds("fight", 1, 2)

        self.assertEqual(walk_bounds, (-0.22, 0.0))
        self.assertEqual(fight_bounds, (0.0, 0.0))

    def test_action_sequence_resolves_ordered_segment_progress(self):
        first = hf_video_provider._resolve_action_segment(0, 72, 3)
        middle = hf_video_provider._resolve_action_segment(30, 72, 3)
        last = hf_video_provider._resolve_action_segment(71, 72, 3)

        self.assertEqual(first, (0, 0.0))
        self.assertEqual(middle[0], 1)
        self.assertEqual(last, (2, 1.0))


if __name__ == "__main__":
    unittest.main()
